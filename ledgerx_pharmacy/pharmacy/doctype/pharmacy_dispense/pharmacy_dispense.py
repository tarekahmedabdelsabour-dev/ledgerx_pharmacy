import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, nowdate

from ledgerx_pharmacy import data
from ledgerx_pharmacy.engine.pricing import line_amount, r2, split_insurance
from ledgerx_pharmacy.engine.refill import next_due, refill_status


class PharmacyDispense(Document):
	# ------------------------------------------------------------------ validation
	def validate(self):
		branch = data.branch_doc(self.branch)
		if not branch.active:
			frappe.throw(_("Branch {0} is not active").format(self.branch))
		if not self.customer:
			self.customer = data.settings().walk_in_customer
		if not self.customer:
			frappe.throw(_("Choose the patient or set a walk-in customer in Pharmacy Settings"))
		plan = frappe.get_cached_doc("Insurance Plan", self.insurance_plan) if self.insurance_plan else None
		if plan:
			if not plan.active:
				frappe.throw(_("Insurance plan {0} is not active").format(plan.name))
			if plan.valid_to and getdate(plan.valid_to) < getdate(self.posting_date):
				frappe.throw(_("Insurance plan {0} expired on {1}").format(plan.name, plan.valid_to))
			if not frappe.db.get_value("Insurance Company", plan.insurance_company, "active"):
				frappe.throw(_("Insurance company {0} is not active").format(plan.insurance_company))
		if not self.items:
			frappe.throw(_("Add at least one item"))
		for r in self.items:
			info = data.item_info(r.item_code)
			if info.disabled:
				frappe.throw(_("Item {0} is disabled").format(r.item_code))
			if not info.is_stock_item:
				frappe.throw(_("Item {0} is not a stock item").format(r.item_code))
			if flt(r.qty) <= 0:
				frappe.throw(_("Row {0}: quantity must be more than zero").format(r.idx))
			r.item_name = info.item_name
			r.uom = r.uom or info.stock_uom
			r.conversion_factor = data.conversion_factor(r.item_code, r.uom)
			r.klass = info.ph_class
			r.is_controlled = info.controlled
			if not flt(r.price):
				r.price = data.public_price(r.item_code, self.branch, r.uom)
			if not flt(r.price):
				frappe.throw(_("Row {0}: {1} has no public price").format(r.idx, r.item_code))
			if flt(r.discount_pct) < 0 or flt(r.discount_pct) > 100:
				frappe.throw(_("Row {0}: discount must be between 0 and 100").format(r.idx))
			r.amount = line_amount(r.price, r.qty, r.discount_pct)
			if plan and plan.exclude_cosmetics and r.klass in ("Cosmetic", "Supplement"):
				r.covered = 0
		if any(r.is_controlled for r in self.items) and data.settings().controlled_needs_prescription:
			cust_id = self.patient_id or frappe.db.get_value("Customer", self.customer, "ph_national_id")
			self.patient_id = cust_id
			missing = [lbl for lbl, v in ((_("Prescription No."), self.prescription_no), (_("Doctor"), self.doctor), (_("Patient National ID"), cust_id)) if not v]
			if missing:
				frappe.throw(_("Controlled drugs need: {0}").format(", ".join(missing)))
		lines = [{"amount": r.amount, "covered": bool(r.covered), "klass": r.klass} for r in self.items]
		if plan:
			s = split_insurance(lines, plan.cover_pct, plan.patient_cap, plan.min_copay, False)
		else:
			s = split_insurance([{"amount": x["amount"], "covered": False} for x in lines], 0)
		self.gross_total, self.insurer_share, self.patient_share = s["gross"], s["insurer"], s["patient"]
		if self.amount_received and flt(self.amount_received) > flt(self.patient_share) + 0.005:
			frappe.throw(_("The amount received cannot be more than what the patient pays ({0})").format(self.patient_share))

	def before_submit(self):
		self._allocate()

	# ------------------------------------------------------------------ stock
	def _allocate(self):
		"""Picks batches first-expiry-first-out per row; throws one clear message listing everything that is short."""
		branch = data.branch_doc(self.branch)
		wh = branch.warehouse
		self._plan = []  # (row, [(batch, stock_qty)])
		short, used = [], {}
		for r in self.items:
			need = flt(r.qty) * flt(r.conversion_factor)
			rows = data.batch_stock([wh], r.item_code) if cint(frappe.db.get_value("Item", r.item_code, "has_batch_no")) else None
			if rows is not None:
				from ledgerx_pharmacy.engine.stock import fefo_allocate

				left = [{"batch_no": b["batch_no"], "qty": b["qty"] - used.get((r.item_code, b["batch_no"]), 0), "expiry": b["expiry"]} for b in rows]
				alloc, miss = fefo_allocate(left, need, getdate(self.posting_date), cint(data.settings().min_days_to_sell))
				for b, q in alloc:
					used[(r.item_code, b)] = used.get((r.item_code, b), 0) + q
			else:
				have = flt(frappe.db.get_value("Bin", {"item_code": r.item_code, "warehouse": wh}, "actual_qty")) - used.get((r.item_code, None), 0)
				take = max(min(have, need), 0)
				alloc, miss = ([(None, take)] if take > 0 else []), need - take
				used[(r.item_code, None)] = used.get((r.item_code, None), 0) + take
			if miss > 1e-6:
				short.append(f"{r.item_code}: {flt(miss / flt(r.conversion_factor), 3)}")
			self._plan.append((r, alloc))
			r.batches = ", ".join(f"{b} x{flt(q, 3)}" for b, q in alloc if b) or ""
		if short:
			frappe.throw(_("Not enough usable stock in {0} (expired batches are never sold): {1}").format(branch.branch_name, "; ".join(short)), title=_("Insufficient Stock"))

	# ------------------------------------------------------------------ accounting
	def on_submit(self):
		si = self._make_invoice()
		self.db_set("sales_invoice", si.name)
		insurer = flt(self.insurer_share)
		if insurer > 0:
			je = self._make_insurer_entry(si, insurer)
			self.db_set("insurer_entry", je.name)
		si.reload()
		pay = flt(self.amount_received) if self.amount_received else flt(self.patient_share)
		pay = min(pay, flt(si.outstanding_amount))
		if pay > 0.005:
			pe = self._make_payment(si, pay)
			self.db_set("payment_entry", pe.name)
		self._update_refills()

	def _make_invoice(self):
		branch = data.branch_doc(self.branch)
		s = data.settings()
		si = frappe.new_doc("Sales Invoice")
		si.customer = self.customer
		si.company = branch.company
		si.posting_date = self.posting_date
		si.set_posting_time = 1
		si.update_stock = 1
		si.set_warehouse = branch.warehouse
		if branch.cost_center:
			si.cost_center = branch.cost_center
		si.selling_price_list = branch.price_list or s.public_price_list
		si.ignore_pricing_rule = 1
		si.ph_branch = self.branch
		si.ph_prescription_no = self.prescription_no
		si.ph_doctor = self.doctor
		si.ph_patient_id = self.patient_id
		si.remarks = _("Pharmacy dispense {0}").format(self.name)
		expected = 0.0
		for r, alloc in self._plan:
			cf = flt(r.conversion_factor)
			for batch, sq in alloc:
				qty = sq / cf
				row = {"item_code": r.item_code, "uom": r.uom, "conversion_factor": cf, "qty": qty, "price_list_rate": flt(r.price), "discount_percentage": flt(r.discount_pct),
					"rate": r2(flt(r.price) * (1 - flt(r.discount_pct) / 100.0)), "warehouse": branch.warehouse}
				if branch.cost_center:
					row["cost_center"] = branch.cost_center
				if batch:
					row.update({"batch_no": batch, "use_serial_batch_fields": 1})
				si.append("items", row)
				expected += qty * row["rate"]
		if s.sales_taxes_template:
			si.taxes_and_charges = s.sales_taxes_template
			si.set_taxes()
		si.insert(ignore_permissions=True)
		if abs(sum(flt(i.amount) for i in si.items) - expected) > 0.05 * max(len(si.items), 1):
			frappe.throw(_("The invoice prices do not match the dispense prices. Check pricing rules and the price list, then try again."))
		si.submit()
		return si

	def _make_insurer_entry(self, si, amount):
		plan = frappe.get_cached_doc("Insurance Plan", self.insurance_plan)
		insurer_customer = frappe.db.get_value("Insurance Company", plan.insurance_company, "customer")
		from erpnext.accounts.party import get_party_account

		cc = data.branch_doc(self.branch).cost_center
		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.company = si.company
		je.posting_date = self.posting_date
		je.user_remark = _("Insurance share of {0} ({1})").format(self.name, plan.name)
		common = {"cost_center": cc} if cc else {}
		je.append("accounts", {"account": get_party_account("Customer", insurer_customer, si.company), "party_type": "Customer", "party": insurer_customer, "debit_in_account_currency": amount, **common})
		je.append("accounts", {"account": si.debit_to, "party_type": "Customer", "party": si.customer, "credit_in_account_currency": amount,
			"reference_type": "Sales Invoice", "reference_name": si.name, **common})
		je.insert(ignore_permissions=True)
		je.submit()
		return je

	def _make_payment(self, si, amount):
		from erpnext.accounts.doctype.sales_invoice.sales_invoice import get_bank_cash_account

		mode = self.mode_of_payment or "Cash"
		cur = frappe.get_cached_value("Company", si.company, "default_currency")
		pe = frappe.new_doc("Payment Entry")
		pe.payment_type = "Receive"
		pe.company = si.company
		pe.posting_date = self.posting_date
		pe.mode_of_payment = mode
		pe.party_type = "Customer"
		pe.party = si.customer
		pe.paid_from = si.debit_to
		pe.paid_to = get_bank_cash_account(mode, si.company)["account"]
		pe.paid_from_account_currency = pe.paid_to_account_currency = cur
		pe.paid_amount = pe.received_amount = amount
		pe.source_exchange_rate = pe.target_exchange_rate = 1
		pe.reference_no = self.name
		pe.reference_date = self.posting_date
		cc = data.branch_doc(self.branch).cost_center
		if cc:
			pe.cost_center = cc
		pe.append("references", {"reference_doctype": "Sales Invoice", "reference_name": si.name, "total_amount": si.grand_total, "outstanding_amount": si.outstanding_amount, "allocated_amount": amount})
		pe.insert(ignore_permissions=True)
		pe.submit()
		return pe

	def on_cancel(self):
		self.flags.ignore_links = True
		for dt, fld in (("Payment Entry", "payment_entry"), ("Journal Entry", "insurer_entry"), ("Sales Invoice", "sales_invoice")):
			name = self.get(fld)
			if name and frappe.db.get_value(dt, name, "docstatus") == 1:
				d = frappe.get_doc(dt, name)
				d.flags.ignore_links = True
				d.cancel()
		self._update_refills(undo=True)

	# ------------------------------------------------------------------ chronic patients
	def _update_refills(self, undo=False):
		if not self.customer or self.customer == data.settings().walk_in_customer:
			return
		items = [r.item_code for r in self.items]
		for name in frappe.get_all("Refill Plan", filters={"customer": self.customer, "item_code": ["in", items], "stopped": 0}, pluck="name"):
			plan = frappe.get_doc("Refill Plan", name)
			if undo:
				last = frappe.db.sql("""SELECT MAX(d.posting_date) FROM `tabPharmacy Dispense` d INNER JOIN `tabDispense Item` i ON i.parent = d.name
					WHERE d.docstatus = 1 AND d.name != %s AND d.customer = %s AND i.item_code = %s""", (self.name, self.customer, plan.item_code))[0][0]
				plan.last_dispensed = last
			elif not plan.last_dispensed or getdate(self.posting_date) >= getdate(plan.last_dispensed):
				plan.last_dispensed = self.posting_date
			plan.save(ignore_permissions=True)
