import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not (filters.from_date and filters.to_date):
		frappe.throw(_("Choose the dates"))
	cond, vals = "", {"f": filters.from_date, "t": filters.to_date}
	if filters.branch:
		cond = " AND si.ph_branch = %(b)s"
		vals["b"] = filters.branch
	if filters.company:
		cond += " AND si.company = %(c)s"
		vals["c"] = filters.company
	rows = frappe.db.sql(
		f"""SELECT si.ph_branch AS branch, COUNT(DISTINCT si.name) AS invoices, SUM(sii.net_amount) AS sales, SUM(sii.stock_qty * sii.incoming_rate) AS cost
		FROM `tabSales Invoice` si INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE si.docstatus = 1 AND ifnull(si.ph_branch, '') != '' AND si.posting_date BETWEEN %(f)s AND %(t)s {cond}
		GROUP BY si.ph_branch ORDER BY sales DESC""", vals, as_dict=1)
	ins = {r.branch: flt(r.s) for r in frappe.db.sql("""SELECT branch, SUM(insurer_share) s FROM `tabPharmacy Dispense` WHERE docstatus = 1 AND posting_date BETWEEN %(f)s AND %(t)s GROUP BY branch""", vals, as_dict=1)}
	out = []
	for r in rows:
		sales, cost = flt(r.sales), flt(r.cost)
		out.append({"branch": r.branch, "invoices": r.invoices, "sales": sales, "cost": cost, "margin": round(sales - cost, 2), "margin_pct": round((sales - cost) / sales * 100, 1) if sales else 0,
			"basket": round(sales / r.invoices, 2) if r.invoices else 0, "insurer": ins.get(r.branch, 0.0)})
	cols = [
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Pharmacy Branch", "width": 160},
		{"label": _("Invoices"), "fieldname": "invoices", "fieldtype": "Int", "width": 90},
		{"label": _("Sales"), "fieldname": "sales", "fieldtype": "Currency", "width": 120},
		{"label": _("Cost of Goods"), "fieldname": "cost", "fieldtype": "Currency", "width": 120},
		{"label": _("Margin"), "fieldname": "margin", "fieldtype": "Currency", "width": 110},
		{"label": _("Margin %"), "fieldname": "margin_pct", "fieldtype": "Percent", "width": 90},
		{"label": _("Average Invoice"), "fieldname": "basket", "fieldtype": "Currency", "width": 110},
		{"label": _("Charged to Insurers"), "fieldname": "insurer", "fieldtype": "Currency", "width": 130},
	]
	chart = {"data": {"labels": [r["branch"] for r in out], "datasets": [{"name": _("Sales"), "values": [r["sales"] for r in out]}, {"name": _("Margin"), "values": [r["margin"] for r in out]}]}, "type": "bar"}
	return cols, out, None, chart
