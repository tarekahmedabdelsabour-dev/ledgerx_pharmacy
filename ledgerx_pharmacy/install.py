"""Install and migrate steps. Each is idempotent and a failing step never aborts a migrate."""
import os

import frappe

MODULE = "Pharmacy"
FOLDER = "pharmacy"
ROLES = ["Pharmacy Manager", "Pharmacist", "Pharmacy Assistant", "Pharmacy Buyer"]
WALK_IN = "Pharmacy Walk-in"
KLASSES = "Prescription\nOTC\nControlled\nCosmetic\nSupplement\nMedical Supply"
FORMS = "\nTablet\nCapsule\nSyrup\nSuspension\nInjection\nCream\nOintment\nGel\nDrops\nSpray\nInhaler\nSuppository\nSachet\nOther"

FIELDS = [
	# Item
	("Item", "ph_section", {"label": "Pharmacy", "fieldtype": "Section Break", "insert_after": "item_name", "collapsible": 1}),
	("Item", "ph_is_drug", {"label": "Pharmacy Product", "fieldtype": "Check", "insert_after": "ph_section", "description": "Turns on batch and expiry tracking."}),
	("Item", "ph_class", {"label": "Pharmacy Class", "fieldtype": "Select", "options": KLASSES, "insert_after": "ph_is_drug", "depends_on": "ph_is_drug", "in_standard_filter": 1}),
	("Item", "ph_active_ingredient", {"label": "Active Ingredient", "fieldtype": "Link", "options": "Active Ingredient", "insert_after": "ph_class", "depends_on": "ph_is_drug", "in_standard_filter": 1}),
	("Item", "ph_col", {"fieldtype": "Column Break", "insert_after": "ph_active_ingredient"}),
	("Item", "ph_strength", {"label": "Strength", "fieldtype": "Data", "insert_after": "ph_col", "depends_on": "ph_is_drug", "description": "Example: 500 mg"}),
	("Item", "ph_form", {"label": "Dosage Form", "fieldtype": "Select", "options": FORMS, "insert_after": "ph_strength", "depends_on": "ph_is_drug"}),
	("Item", "ph_public_price", {"label": "Public Price", "fieldtype": "Currency", "insert_after": "ph_form", "depends_on": "ph_is_drug", "description": "The official price printed on the pack. Kept in the public price list."}),
	("Item", "ph_cold_chain", {"label": "Keep Refrigerated", "fieldtype": "Check", "insert_after": "ph_public_price", "depends_on": "ph_is_drug"}),
	# Customer (patient)
	("Customer", "ph_section", {"label": "Patient", "fieldtype": "Section Break", "insert_after": "customer_details", "collapsible": 1}),
	("Customer", "ph_national_id", {"label": "National ID", "fieldtype": "Data", "insert_after": "ph_section"}),
	("Customer", "ph_insurance_plan", {"label": "Insurance Plan", "fieldtype": "Link", "options": "Insurance Plan", "insert_after": "ph_national_id"}),
	("Customer", "ph_col", {"fieldtype": "Column Break", "insert_after": "ph_insurance_plan"}),
	("Customer", "ph_member_no", {"label": "Insurance Member No.", "fieldtype": "Data", "insert_after": "ph_col"}),
	("Customer", "ph_chronic_notes", {"label": "Chronic Conditions / Allergies", "fieldtype": "Small Text", "insert_after": "ph_member_no"}),
	# Sales Invoice (also filled by the Pharmacy POS sale)
	("Sales Invoice", "ph_section", {"label": "Pharmacy", "fieldtype": "Section Break", "insert_after": "more_info", "collapsible": 1}),
	("Sales Invoice", "ph_branch", {"label": "Pharmacy Branch", "fieldtype": "Link", "options": "Pharmacy Branch", "insert_after": "ph_section", "in_standard_filter": 1}),
	("Sales Invoice", "ph_prescription_no", {"label": "Prescription No.", "fieldtype": "Data", "insert_after": "ph_branch"}),
	("Sales Invoice", "ph_col", {"fieldtype": "Column Break", "insert_after": "ph_prescription_no"}),
	("Sales Invoice", "ph_doctor", {"label": "Doctor", "fieldtype": "Data", "insert_after": "ph_col"}),
	("Sales Invoice", "ph_patient_id", {"label": "Patient National ID", "fieldtype": "Data", "insert_after": "ph_doctor"}),
]


def check_app_permission():
	if frappe.session.user == "Administrator":
		return True
	return bool(set(frappe.get_roles()) & set(ROLES + ["System Manager", "Stock Manager", "Stock User", "Purchase Manager"]))


def after_install():
	_all()


def after_migrate():
	_all()


def _all():
	for fn in (ensure_module, ensure_roles, ensure_custom_fields, ensure_walk_in, ensure_settings, refresh_workspace):
		try:
			fn()
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"ledgerx_pharmacy install step failed: {fn.__name__}")
	frappe.clear_cache()


def ensure_module():
	if not frappe.db.exists("Module Def", MODULE):
		frappe.get_doc({"doctype": "Module Def", "module_name": MODULE, "app_name": "ledgerx_pharmacy"}).insert(ignore_permissions=True)


def ensure_roles():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)


def ensure_custom_fields():
	for dt, name, spec in FIELDS:
		if frappe.db.exists("DocType", dt) and not frappe.db.exists("Custom Field", {"dt": dt, "fieldname": name}):
			frappe.get_doc({"doctype": "Custom Field", "dt": dt, "fieldname": name, **spec}).insert(ignore_permissions=True)


def ensure_walk_in():
	if frappe.db.exists("Customer", WALK_IN):
		return
	group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
	territory = frappe.db.get_value("Territory", {"is_group": 0}, "name")
	if group and territory:
		frappe.get_doc({"doctype": "Customer", "customer_name": WALK_IN, "customer_type": "Individual", "customer_group": group, "territory": territory}).insert(ignore_permissions=True)


def ensure_settings():
	s = frappe.get_doc("Pharmacy Settings")
	changed = False
	if not s.company:
		s.company = frappe.db.get_single_value("Global Defaults", "default_company") or frappe.db.get_value("Company", {}, "name")
		changed = bool(s.company)
	if not s.public_price_list:
		pl = "Standard Selling" if frappe.db.exists("Price List", "Standard Selling") else frappe.db.get_value("Price List", {"selling": 1, "enabled": 1}, "name")
		if pl:
			s.public_price_list, changed = pl, True
	if not s.walk_in_customer and frappe.db.exists("Customer", WALK_IN):
		s.walk_in_customer, changed = WALK_IN, True
	if changed and s.company:
		s.save(ignore_permissions=True)


def refresh_workspace():
	"""Migrate only re-reads a workspace file that is newer than the saved one: force it."""
	base = os.path.join(frappe.get_app_path("ledgerx_pharmacy"), FOLDER)
	for dt in ("number_card", "dashboard_chart"):
		folder = os.path.join(base, dt)
		for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
			if os.path.isdir(os.path.join(folder, name)):
				frappe.reload_doc(FOLDER, dt, name, force=True)
	frappe.reload_doc(FOLDER, "workspace", "pharmacy", force=True)
