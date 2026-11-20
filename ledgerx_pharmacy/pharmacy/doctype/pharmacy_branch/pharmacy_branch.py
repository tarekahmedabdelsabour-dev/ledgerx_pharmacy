import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, getdate, nowdate


class PharmacyBranch(Document):
	def validate(self):
		for fld in ("warehouse", "expired_warehouse"):
			wh = self.get(fld)
			if wh and frappe.db.get_value("Warehouse", wh, "company") != self.company:
				frappe.throw(_("Warehouse {0} does not belong to {1}").format(wh, self.company))
		if self.expired_warehouse and self.expired_warehouse == self.warehouse:
			frappe.throw(_("The expired stock warehouse must be different from the sales warehouse"))
		other = frappe.db.get_value("Pharmacy Branch", {"warehouse": self.warehouse, "name": ["!=", self.name]}, "name")
		if other:
			frappe.throw(_("Warehouse {0} already belongs to branch {1}").format(self.warehouse, other))
		if self.license_expiry and getdate(self.license_expiry) < getdate(nowdate()) and self.active:
			frappe.msgprint(_("The license of this branch has expired"), indicator="orange", alert=True)
