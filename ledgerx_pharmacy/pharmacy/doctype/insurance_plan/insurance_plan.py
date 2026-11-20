import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class InsurancePlan(Document):
	def validate(self):
		if not 0 <= flt(self.cover_pct) <= 100:
			frappe.throw(_("Insurer Pays % must be between 0 and 100"))
		if flt(self.patient_cap) < 0 or flt(self.min_copay) < 0:
			frappe.throw(_("Amounts cannot be negative"))
