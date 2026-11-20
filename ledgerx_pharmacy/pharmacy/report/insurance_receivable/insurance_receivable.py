import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from ledgerx_pharmacy.engine.aging import fifo_aging


def execute(filters=None):
	filters = frappe._dict(filters or {})
	as_of = getdate(filters.as_of or nowdate())
	company = filters.company
	insurers = frappe.get_all("Insurance Company", filters={"name": filters.insurance_company} if filters.insurance_company else {}, fields=["name", "customer"])
	out = []
	for ins in insurers:
		if not ins.customer:
			continue
		cond, vals = "", {"p": ins.customer, "d": as_of}
		if company:
			cond = " AND company = %(c)s"
			vals["c"] = company
		deb = frappe.db.sql(f"""SELECT posting_date, SUM(debit) a FROM `tabGL Entry` WHERE party_type = 'Customer' AND party = %(p)s AND is_cancelled = 0 AND posting_date <= %(d)s {cond}
			GROUP BY posting_date HAVING SUM(debit) > 0""", vals)
		cred = frappe.db.sql(f"""SELECT SUM(credit) FROM `tabGL Entry` WHERE party_type = 'Customer' AND party = %(p)s AND is_cancelled = 0 AND posting_date <= %(d)s {cond}""", vals)[0][0]
		# debit entries that reverse an earlier credit would be netted: keep them simple, the report shows what is still owed overall
		r = fifo_aging([(getdate(d), flt(a)) for d, a in deb], flt(cred), as_of)
		if r["total"] or r["unapplied"]:
			out.append({"insurance_company": ins.name, "customer": ins.customer, "b0": r["buckets"][0], "b1": r["buckets"][1], "b2": r["buckets"][2], "b3": r["buckets"][3], "total": r["total"], "unapplied": r["unapplied"]})
	cols = [
		{"label": _("Insurance Company"), "fieldname": "insurance_company", "fieldtype": "Link", "options": "Insurance Company", "width": 180},
		{"label": _("Customer Account"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 160},
		{"label": _("0 - 30 days"), "fieldname": "b0", "fieldtype": "Currency", "width": 110},
		{"label": _("31 - 60 days"), "fieldname": "b1", "fieldtype": "Currency", "width": 110},
		{"label": _("61 - 90 days"), "fieldname": "b2", "fieldtype": "Currency", "width": 110},
		{"label": _("Over 90 days"), "fieldname": "b3", "fieldtype": "Currency", "width": 110},
		{"label": _("Total Owed"), "fieldname": "total", "fieldtype": "Currency", "width": 120},
		{"label": _("Paid in Advance"), "fieldname": "unapplied", "fieldtype": "Currency", "width": 120},
	]
	return cols, out
