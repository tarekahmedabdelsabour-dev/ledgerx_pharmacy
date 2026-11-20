import frappe
from frappe import _
from frappe.model.document import Document


class InsuranceCompany(Document):
	def before_validate(self):
		if self.customer:
			return
		group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
		territory = frappe.db.get_value("Territory", {"is_group": 0}, "name")
		if not (group and territory):
			frappe.throw(_("Create a customer group and a territory first, or choose the customer account yourself"))
		existing = frappe.db.get_value("Customer", {"customer_name": self.company_name}, "name")
		if existing:
			self.customer = existing
			return
		c = frappe.get_doc({"doctype": "Customer", "customer_name": self.company_name, "customer_type": "Company", "customer_group": group, "territory": territory})
		c.insert(ignore_permissions=True)
		self.customer = c.name
