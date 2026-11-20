import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	f = {}
	if filters.branch:
		f["branch"] = filters.branch
	if filters.item_code:
		f["item_code"] = filters.item_code
	if filters.from_date and filters.to_date:
		f["posting_date"] = ["between", [filters.from_date, filters.to_date]]
	if not filters.include_cancelled:
		f["cancelled"] = 0
	rows = frappe.get_all("Controlled Drug Log", filters=f, fields=["posting_date", "branch", "item_code", "item_name", "batch_no", "qty", "balance_after", "customer", "patient_id", "doctor", "prescription_no", "sales_invoice", "cancelled"],
		order_by="posting_date asc, creation asc", limit_page_length=0)
	cols = [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Pharmacy Branch", "width": 120},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 170},
		{"label": _("Batch"), "fieldname": "batch_no", "fieldtype": "Data", "width": 100},
		{"label": _("Quantity"), "fieldname": "qty", "fieldtype": "Float", "width": 80},
		{"label": _("Balance After"), "fieldname": "balance_after", "fieldtype": "Float", "width": 100},
		{"label": _("Patient"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 140},
		{"label": _("Patient National ID"), "fieldname": "patient_id", "fieldtype": "Data", "width": 130},
		{"label": _("Doctor"), "fieldname": "doctor", "fieldtype": "Data", "width": 120},
		{"label": _("Prescription No."), "fieldname": "prescription_no", "fieldtype": "Data", "width": 120},
		{"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 130},
		{"label": _("Cancelled"), "fieldname": "cancelled", "fieldtype": "Check", "width": 80},
	]
	return cols, rows
