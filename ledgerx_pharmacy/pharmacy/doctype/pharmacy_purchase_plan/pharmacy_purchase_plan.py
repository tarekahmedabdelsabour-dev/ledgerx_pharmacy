from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, flt, getdate, nowdate

from ledgerx_pharmacy import data
from ledgerx_pharmacy.engine.replenish import best_offer, effective_cost, order_qty, paid_units


class PharmacyPurchasePlan(Document):
	def validate(self):
		s = data.settings()
		self.cover_days = cint(self.cover_days) or cint(s.cover_days) or 14
		self.lookback_days = cint(self.lookback_days) or cint(s.sales_lookback_days) or 60
		for r in self.rows:
			r.amount = round(flt(r.order_qty) * flt(r.unit_cost), 2)
		self.total_amount = sum(flt(r.amount) for r in self.rows if r.include)

	def _branches(self):
		ids = [b.branch for b in self.branches] or None
		rows = data.active_branches(ids)
		recv = data.branch_doc(self.receiving_branch)
		if recv.name not in [b.name for b in rows]:
			rows.append(frappe._dict(name=recv.name, warehouse=recv.warehouse, company=recv.company))
		return rows

	@frappe.whitelist()
	def load_needs(self):
		"""Counts stock, orders and sales of the chosen branches and proposes what to buy and from whom."""
		if self.status == "Ordered":
			frappe.throw(_("Orders were already created from this plan"))
		self.check_permission("write")
		self.validate()
		whs = data.warehouses_of(self._branches())
		stock = data.stock_by_item(whs)
		on_order = data.on_order_by_item(whs)
		sales = data.daily_sales(whs, self.lookback_days)
		levels = data.reorder_levels(whs)
		today = getdate(self.posting_date or nowdate())
		self.rows = []
		notes = []
		for item in sorted(set(sales) | set(levels)):
			info = frappe.db.get_value("Item", item, ["item_name", "disabled", "is_stock_item", "end_of_life"], as_dict=1)
			if not info or info.disabled or not info.is_stock_item or (info.end_of_life and getdate(info.end_of_life) < today):
				continue
			lv, rq = levels.get(item, (0.0, 0.0))
			qty = order_qty(stock.get(item, 0.0), on_order.get(item, 0.0), sales.get(item, 0.0), self.cover_days, lv, 0.0, data.pack_size(item))
			if qty <= 0:
				continue
			base = data.last_purchase_rate(item)
			offers = data.offers_for(item, today)
			best = best_offer(offers, qty, base, today)
			row = {"include": 1, "item_code": item, "item_name": info.item_name, "stock": stock.get(item, 0.0), "on_order": on_order.get(item, 0.0), "daily_sales": sales.get(item, 0.0), "order_qty": qty}
			if best:
				o = next(x for x in offers if x["name"] == best["offer"])
				paid = paid_units(qty, o)
				bonus = (paid // o["bonus_per"]) * o["bonus_qty"] if o.get("bonus_per") and o.get("bonus_qty") else 0
				eff = effective_cost(o, paid, base, today)
				row.update({"supplier": best["supplier"], "order_qty": paid + bonus, "bonus_qty": bonus, "offer": best["offer"], "unit_cost": eff[0] if eff else best["cost"]})
				row["note"] = _("Cheapest offer")
			else:
				sup = data.supplier_for(item)
				row.update({"supplier": sup, "unit_cost": base})
				if not sup:
					row.update({"include": 0, "note": _("No supplier: choose one")})
				elif not base:
					row.update({"include": 0, "note": _("No purchase price yet: enter the cost")})
			self.append("rows", row)
		self.status = "Loaded"
		self.notes_html = _("Needs are counted for {0} (sales of the last {1} days, covering {2} days). Check the quantities and suppliers, then create the purchase orders.").format(", ".join(b.name for b in self._branches()), self.lookback_days, self.cover_days)
		self.validate()
		self.save()
		return len(self.rows)

	@frappe.whitelist()
	def create_orders(self):
		"""One draft purchase order per supplier for the rows that are ticked."""
		self.check_permission("write")
		self.validate()
		if self.status == "Ordered":
			frappe.throw(_("Orders were already created from this plan"))
		recv = data.branch_doc(self.receiving_branch)
		groups = defaultdict(list)
		for r in self.rows:
			if not r.include:
				continue
			if not r.supplier:
				frappe.throw(_("Row {0}: choose a supplier").format(r.idx))
			if flt(r.order_qty) <= 0 or flt(r.unit_cost) <= 0:
				frappe.throw(_("Row {0}: quantity and cost must be more than zero").format(r.idx))
			groups[r.supplier].append(r)
		if not groups:
			frappe.throw(_("Nothing is ticked to order"))
		made = []
		for supplier, rows in groups.items():
			po = frappe.new_doc("Purchase Order")
			po.supplier = supplier
			po.company = recv.company
			po.transaction_date = self.posting_date
			po.schedule_date = add_days(self.posting_date, 7)
			po.set_warehouse = recv.warehouse
			po.remarks = _("From pharmacy purchase plan {0}").format(self.name)
			for r in rows:
				stock_uom = frappe.db.get_value("Item", r.item_code, "stock_uom")
				# order_qty already counts the free units and unit_cost is the cost per unit received
				po.append("items", {"item_code": r.item_code, "qty": flt(r.order_qty), "uom": stock_uom, "stock_uom": stock_uom, "conversion_factor": 1,
					"rate": flt(r.unit_cost), "warehouse": recv.warehouse, "schedule_date": po.schedule_date})
			po.insert(ignore_permissions=True)
			made.append(po.name)
		self.orders_made = "\n".join(made)
		self.status = "Ordered"
		self.save()
		return made
