import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	f = {"stopped": 0}
	f["status"] = filters.status if filters.status else ["in", ["Overdue", "Due Soon"]]
	if filters.branch:
		f["branch"] = filters.branch
	rows = frappe.get_all("Refill Plan", filters=f, fields=["name", "customer", "item_code", "item_name", "qty", "every_days", "last_dispensed", "next_due", "status", "branch"], order_by="next_due asc", limit_page_length=0)
	phones = {r.name: r.mobile_no for r in frappe.get_all("Customer", filters={"name": ["in", list({x.customer for x in rows})]}, fields=["name", "mobile_no"])} if rows else {}
	for r in rows:
		r["mobile"] = phones.get(r.customer)
	cols = [
		{"label": _("Refill Plan"), "fieldname": "name", "fieldtype": "Link", "options": "Refill Plan", "width": 110},
		{"label": _("Patient"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 160},
		{"label": _("Phone"), "fieldname": "mobile", "fieldtype": "Data", "width": 110},
		{"label": _("Medicine"), "fieldname": "item_name", "fieldtype": "Data", "width": 190},
		{"label": _("Quantity"), "fieldname": "qty", "fieldtype": "Float", "width": 80},
		{"label": _("Last Dispensed"), "fieldname": "last_dispensed", "fieldtype": "Date", "width": 110},
		{"label": _("Next Refill Due"), "fieldname": "next_due", "fieldtype": "Date", "width": 110},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Pharmacy Branch", "width": 120},
	]
	return cols, rows
