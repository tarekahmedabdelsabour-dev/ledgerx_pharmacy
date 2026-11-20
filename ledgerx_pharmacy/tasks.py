import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate, nowdate

from ledgerx_pharmacy import data
from ledgerx_pharmacy.engine.stock import expiry_status


def refresh_refills():
	"""Statuses move with time: bring every active refill plan up to date."""
	for name in frappe.get_all("Refill Plan", filters={"stopped": 0}, pluck="name"):
		try:
			doc = frappe.get_doc("Refill Plan", name)
			before = (doc.status, doc.next_due)
			doc.refresh_status()
			if (doc.status, doc.next_due) != before:
				doc.db_set({"status": doc.status, "next_due": doc.next_due}, update_modified=False)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"refill status failed: {name}")


def _users_for(branch):
	users = []
	if branch:
		u = frappe.db.get_value("Pharmacy Branch", branch, "manager_user") if frappe.db.has_column("Pharmacy Branch", "manager_user") else None
		if u:
			users.append(u)
	if not users:
		users = [r.parent for r in frappe.get_all("Has Role", filters={"role": "Pharmacy Manager", "parenttype": "User"}, fields=["parent"])]
	return [u for u in set(users) if frappe.db.get_value("User", u, "enabled")]


def _todo(user, description, ref_type, ref_name):
	if frappe.db.exists("ToDo", {"reference_type": ref_type, "reference_name": ref_name, "allocated_to": user, "status": "Open"}):
		return
	frappe.get_doc({"doctype": "ToDo", "allocated_to": user, "description": description, "reference_type": ref_type, "reference_name": ref_name, "priority": "Medium", "date": nowdate()}).insert(ignore_permissions=True)


def refill_reminders():
	"""One reminder (a ToDo for the branch manager) when a chronic patient's refill is due or overdue; repeated weekly while still due."""
	today = getdate(nowdate())
	for p in frappe.get_all("Refill Plan", filters={"stopped": 0, "status": ["in", ["Due Soon", "Overdue"]]}, fields=["name", "customer", "item_name", "next_due", "branch", "last_reminded"]):
		if p.last_reminded and (today - getdate(p.last_reminded)).days < 7:
			continue
		try:
			for u in _users_for(p.branch):
				_todo(u, _("Refill due {0}: {1} - {2}").format(p.next_due, p.customer, p.item_name), "Refill Plan", p.name)
			frappe.db.set_value("Refill Plan", p.name, "last_reminded", today, update_modified=False)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"refill reminder failed: {p.name}")


def expiry_alerts():
	"""Daily: one ToDo per branch manager listing how many batches are expired or about to expire."""
	s = data.settings()
	today = getdate(nowdate())
	for b in data.active_branches():
		counts = {"Expired": 0, "Critical": 0}
		for r in data.batch_stock([b.warehouse]):
			st = expiry_status(r["expiry"], today, cint(s.critical_expiry_days), cint(s.near_expiry_days))
			if st in counts:
				counts[st] += 1
		if not any(counts.values()):
			continue
		try:
			ref = frappe.db.get_value("Pharmacy Branch", b.name, "name")
			for u in _users_for(b.name):
				if frappe.db.exists("ToDo", {"reference_type": "Pharmacy Branch", "reference_name": ref, "allocated_to": u, "status": "Open"}):
					continue
				_todo(u, _("{0}: {1} expired batches and {2} expiring within {3} days. Open the Expiry report.").format(b.name, counts["Expired"], counts["Critical"], s.critical_expiry_days), "Pharmacy Branch", ref)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"expiry alert failed: {b.name}")
