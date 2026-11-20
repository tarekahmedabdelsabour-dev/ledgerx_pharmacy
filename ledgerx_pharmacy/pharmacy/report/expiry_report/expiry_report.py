import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from ledgerx_pharmacy import data
from ledgerx_pharmacy.engine.stock import days_left, expiry_status


def execute(filters=None):
	filters = frappe._dict(filters or {})
	s = data.settings()
	today = getdate(nowdate())
	crit, near = cint(s.critical_expiry_days), cint(s.near_expiry_days)
	branches = data.active_branches([filters.branch] if filters.branch else None)
	wh_branch = {b.warehouse: b.name for b in branches}
	rows = data.batch_stock(list(wh_branch))
	val = {(r.item_code, r.warehouse): flt(r.valuation_rate) for r in frappe.get_all("Bin", filters={"warehouse": ["in", list(wh_branch)]}, fields=["item_code", "warehouse", "valuation_rate"])} if wh_branch else {}
	names = {r.name: r.item_name for r in frappe.get_all("Item", filters={"name": ["in", list({x["item_code"] for x in rows})]}, fields=["name", "item_name"])} if rows else {}
	want = filters.status
	out, total = [], 0.0
	for r in sorted(rows, key=lambda x: (x["expiry"] is None, x["expiry"], x["item_code"])):
		st = expiry_status(r["expiry"], today, crit, near)
		if want and want != "All":
			if want == "Needs Action" and st not in ("Expired", "Critical", "Near Expiry"):
				continue
			if want not in ("Needs Action",) and st != want:
				continue
		elif not want and st in ("OK", "No Expiry"):
			continue
		cost = round(r["qty"] * val.get((r["item_code"], r["warehouse"]), 0.0), 2)
		total += cost
		out.append({"item_code": r["item_code"], "item_name": names.get(r["item_code"]), "batch_no": r["batch_no"], "branch": wh_branch.get(r["warehouse"]), "qty": r["qty"],
			"expiry": r["expiry"], "days_left": days_left(r["expiry"], today), "status": st, "cost": cost})
	cols = [
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 200},
		{"label": _("Batch"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 120},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Pharmacy Branch", "width": 130},
		{"label": _("Quantity"), "fieldname": "qty", "fieldtype": "Float", "width": 90},
		{"label": _("Expiry"), "fieldname": "expiry", "fieldtype": "Date", "width": 100},
		{"label": _("Days Left"), "fieldname": "days_left", "fieldtype": "Int", "width": 90},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": _("Cost at Risk"), "fieldname": "cost", "fieldtype": "Currency", "width": 110},
	]
	msg = _("Cost of the listed stock: {0}").format(frappe.format_value(total, {"fieldtype": "Currency"}))
	return cols, out, msg
