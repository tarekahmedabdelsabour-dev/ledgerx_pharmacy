import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, nowdate

from ledgerx_pharmacy.engine.refill import next_due, refill_status


class RefillPlan(Document):
	def validate(self):
		if cint(self.every_days) <= 0:
			frappe.throw(_("Every (days) must be more than zero"))
		if flt(self.qty) <= 0:
			frappe.throw(_("Quantity per refill must be more than zero"))
		self.refresh_status()

	def refresh_status(self):
		if self.stopped:
			self.status, self.next_due = "Stopped", None
			return
		# never dispensed yet: the first refill is due on the start date; afterwards every N days from the last one
		if self.last_dispensed:
			self.next_due = next_due(getdate(self.last_dispensed), cint(self.every_days))
		else:
			self.next_due = getdate(self.start_date) if self.start_date else None
		lead = cint(frappe.db.get_single_value("Pharmacy Settings", "refill_lead_days"))
		self.status = refill_status(self.next_due, getdate(nowdate()), lead)
