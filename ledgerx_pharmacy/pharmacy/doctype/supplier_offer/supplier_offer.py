import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class SupplierOffer(Document):
	def validate(self):
		if self.valid_from and self.valid_to and getdate(self.valid_from) > getdate(self.valid_to):
			frappe.throw(_("Valid From is after Valid Until"))
		if not 0 <= flt(self.discount_pct) <= 100:
			frappe.throw(_("Discount % must be between 0 and 100"))
		if bool(flt(self.bonus_per)) != bool(flt(self.bonus_qty)):
			frappe.throw(_("Fill both 'For Every' and 'Get Free', or leave both empty"))
		if flt(self.price) < 0 or flt(self.min_qty) < 0:
			frappe.throw(_("Amounts cannot be negative"))
