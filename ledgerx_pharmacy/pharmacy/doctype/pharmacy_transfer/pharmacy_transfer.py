import math

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, nowdate

from ledgerx_pharmacy import data
from ledgerx_pharmacy.engine.replenish import order_qty
from ledgerx_pharmacy.engine.stock import fefo_allocate


class PharmacyTransfer(Document):
	def validate(self):
		fb = data.branch_doc(self.from_branch)
		if self.transfer_type == "Branch Transfer":
			if not self.to_branch:
				frappe.throw(_("Choose the receiving branch"))
			if self.to_branch == self.from_branch:
				frappe.throw(_("The two branches must be different"))
			tb = data.branch_doc(self.to_branch)
			if tb.company != fb.company:
				frappe.throw(_("Both branches must belong to the same company"))
			if not tb.active:
				frappe.throw(_("Branch {0} is not active").format(self.to_branch))
		else:
			self.to_branch = None
			if self.transfer_type == "Move to Expired Stock" and not fb.expired_warehouse:
				frappe.throw(_("Set an expired stock warehouse on branch {0} first").format(self.from_branch))
		if not self.items:
			frappe.throw(_("Add at least one item"))
		for r in self.items:
			info = data.item_info(r.item_code)
			if flt(r.qty) <= 0:
				frappe.throw(_("Row {0}: quantity must be more than zero").format(r.idx))
			r.item_name = info.item_name
			r.uom = r.uom or info.stock_uom
			r.conversion_factor = data.conversion_factor(r.item_code, r.uom)
			if r.batch_no:
				r.expiry_date = frappe.db.get_value("Batch", r.batch_no, "expiry_date")
				if frappe.db.get_value("Batch", r.batch_no, "item") != r.item_code:
					frappe.throw(_("Row {0}: batch {1} belongs to another item").format(r.idx, r.batch_no))
			elif self.transfer_type != "Branch Transfer" and cint(info.has_batch_no):
				frappe.throw(_("Row {0}: choose the batch to move or write off").format(r.idx))

	def before_submit(self):
		self._plan = []
		wh = data.branch_doc(self.from_branch).warehouse
		short, used = [], {}
		for r in self.items:
			need = flt(r.qty) * flt(r.conversion_factor)
			tracked = cint(frappe.db.get_value("Item", r.item_code, "has_batch_no"))
			if not tracked:
				have = flt(frappe.db.get_value("Bin", {"item_code": r.item_code, "warehouse": wh}, "actual_qty")) - used.get((r.item_code, None), 0)
				take = max(min(have, need), 0)
				alloc, miss = ([(None, take)] if take > 0 else []), need - take
				used[(r.item_code, None)] = used.get((r.item_code, None), 0) + take
			else:
				rows = data.batch_stock([wh], r.item_code)
				left = [{"batch_no": b["batch_no"], "qty": b["qty"] - used.get((r.item_code, b["batch_no"]), 0), "expiry": b["expiry"]} for b in rows]
				if r.batch_no:
					left = [b for b in left if b["batch_no"] == r.batch_no]
					# a chosen batch is moved as it is, even when expired
					have = sum(b["qty"] for b in left)
					take = max(min(have, need), 0)
					alloc, miss = ([(r.batch_no, take)] if take > 0 else []), need - take
				else:
					alloc, miss = fefo_allocate(left, need, getdate(self.posting_date), 0)
				for b, q in alloc:
					used[(r.item_code, b)] = used.get((r.item_code, b), 0) + q
			if miss > 1e-6:
				short.append(f"{r.item_code}: {flt(miss / flt(r.conversion_factor), 3)}")
			self._plan.append((r, alloc))
			r.batches = ", ".join(f"{b} x{flt(q, 3)}" for b, q in alloc if b)
		if short:
			frappe.throw(_("Not enough stock in {0}: {1}").format(self.from_branch, "; ".join(short)), title=_("Insufficient Stock"))

	def on_submit(self):
		fb = data.branch_doc(self.from_branch)
		se = frappe.new_doc("Stock Entry")
		se.company = fb.company
		se.posting_date = self.posting_date
		se.set_posting_time = 1
		se.remarks = _("Pharmacy transfer {0}").format(self.name)
		if self.transfer_type == "Write Off":
			se.stock_entry_type = "Material Issue"
			se.from_warehouse = fb.warehouse
			expense = frappe.get_cached_value("Company", fb.company, "stock_adjustment_account")
			if not expense:
				frappe.throw(_("Set the stock adjustment account on company {0}").format(fb.company))
		else:
			se.stock_entry_type = "Material Transfer"
			se.from_warehouse = fb.warehouse
			target = fb.expired_warehouse if self.transfer_type == "Move to Expired Stock" else data.branch_doc(self.to_branch).warehouse
			se.to_warehouse = target
		for r, alloc in self._plan:
			info = data.item_info(r.item_code)
			for batch, q in alloc:
				row = {"item_code": r.item_code, "qty": q, "uom": info.stock_uom, "stock_uom": info.stock_uom, "conversion_factor": 1, "s_warehouse": fb.warehouse}
				if se.stock_entry_type != "Material Issue":
					row["t_warehouse"] = se.to_warehouse
				else:
					row["expense_account"] = expense
					if fb.cost_center:
						row["cost_center"] = fb.cost_center
				if batch:
					row.update({"batch_no": batch, "use_serial_batch_fields": 1})
				se.append("items", row)
		se.insert(ignore_permissions=True)
		se.submit()
		self.db_set("stock_entry", se.name)

	def on_cancel(self):
		self.flags.ignore_links = True
		if self.stock_entry and frappe.db.get_value("Stock Entry", self.stock_entry, "docstatus") == 1:
			se = frappe.get_doc("Stock Entry", self.stock_entry)
			se.flags.ignore_links = True
			se.cancel()


@frappe.whitelist()
def expired_rows(from_branch, within_days=0):
	"""Batches of a branch that are expired (or expire within `within_days`) ready to fill a transfer."""
	frappe.has_permission("Pharmacy Transfer", "create", throw=True)
	wh = data.branch_doc(from_branch).warehouse
	limit = getdate(nowdate())
	from frappe.utils import add_days

	limit = getdate(add_days(nowdate(), cint(within_days)))
	out = []
	for b in sorted(data.batch_stock([wh]), key=lambda x: (x["expiry"] or getdate("2999-12-31"), x["item_code"])):
		if b["expiry"] and b["expiry"] <= limit:
			out.append({"item_code": b["item_code"], "item_name": frappe.db.get_value("Item", b["item_code"], "item_name"), "uom": frappe.db.get_value("Item", b["item_code"], "stock_uom"),
				"qty": b["qty"], "batch_no": b["batch_no"], "expiry_date": b["expiry"]})
	return out


@frappe.whitelist()
def needs_rows(from_branch, to_branch):
	"""What the receiving branch is short of (below its minimum level or its sales cover), limited by what the sending branch can spare."""
	frappe.has_permission("Pharmacy Transfer", "create", throw=True)
	s = data.settings()
	src, dst = data.branch_doc(from_branch), data.branch_doc(to_branch)
	days = cint(s.cover_days) or 14
	sales = data.daily_sales([dst.warehouse], cint(s.sales_lookback_days) or 60)
	levels = data.reorder_levels([dst.warehouse])
	stock_to = data.stock_by_item([dst.warehouse])
	today = getdate(nowdate())
	out = []
	for item in sorted(set(sales) | set(levels)):
		info = frappe.db.get_value("Item", item, ["item_name", "stock_uom", "disabled", "is_stock_item"], as_dict=1)
		if not info or info.disabled or not info.is_stock_item:
			continue
		lv, rq = levels.get(item, (0.0, 0.0))
		want = order_qty(stock_to.get(item, 0.0), 0.0, sales.get(item, 0.0), days, lv, 0.0, 1.0)
		if want <= 0:
			continue
		batches = [{"batch_no": b["batch_no"], "qty": b["qty"], "expiry": b["expiry"]} for b in data.batch_stock([src.warehouse], item)]
		if batches:
			alloc, _short = fefo_allocate(batches, want, today, cint(s.min_days_to_sell))
			give = sum(q for _b, q in alloc)
		else:
			give = min(want, flt(frappe.db.get_value("Bin", {"item_code": item, "warehouse": src.warehouse}, "actual_qty")))
		give = math.floor(give + 1e-9)
		if give > 0:
			out.append({"item_code": item, "item_name": info.item_name, "uom": info.stock_uom, "qty": give})
	return out
