"""Hooks on ERPNext records: Item (batch and expiry), Sales Invoice (controlled drugs, branch)."""
import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate


# ------------------------------------------------------------------ Item
def item_validate(doc, method=None):
	if not cint(doc.get("ph_is_drug")):
		return
	doc.is_stock_item = 1
	if not doc.get("ph_class"):
		doc.ph_class = "OTC"
	# a stock-tracking flag cannot change once stock moved: only set them while the item is still clean
	if doc.is_new() or not frappe.db.exists("Stock Ledger Entry", {"item_code": doc.name}):
		doc.has_batch_no = 1
		doc.has_expiry_date = 1
		doc.create_new_batch = 0


def item_on_update(doc, method=None):
	"""Keep the typed public price in the public price list so every sale and report reads the same number."""
	if not cint(doc.get("ph_is_drug")) or not flt(doc.get("ph_public_price")):
		return
	pl = frappe.db.get_single_value("Pharmacy Settings", "public_price_list")
	if not pl:
		return
	existing = frappe.db.get_value("Item Price", {"item_code": doc.name, "price_list": pl, "uom": doc.stock_uom, "selling": 1}, "name")
	if existing:
		if flt(frappe.db.get_value("Item Price", existing, "price_list_rate")) != flt(doc.ph_public_price):
			frappe.db.set_value("Item Price", existing, "price_list_rate", flt(doc.ph_public_price))
	else:
		frappe.get_doc({"doctype": "Item Price", "item_code": doc.name, "price_list": pl, "price_list_rate": flt(doc.ph_public_price), "uom": doc.stock_uom, "selling": 1}).insert(ignore_permissions=True)


# ------------------------------------------------------------------ Sales Invoice
def _controlled_rows(doc):
	codes = [r.item_code for r in doc.get("items") or [] if r.get("item_code")]
	if not codes:
		return []
	ctrl = set(frappe.get_all("Item", filters={"name": ["in", codes], "ph_class": "Controlled"}, pluck="name"))
	return [r for r in doc.items if r.item_code in ctrl]


def _branch_of(doc):
	if doc.get("ph_branch"):
		return doc.ph_branch
	for r in doc.get("items") or []:
		wh = r.get("warehouse") or doc.get("set_warehouse")
		if wh:
			b = frappe.db.get_value("Pharmacy Branch", {"warehouse": wh}, "name")
			if b:
				return b
	return None


def invoice_validate(doc, method=None):
	if doc.get("is_return") or doc.docstatus != 0:
		return
	if not doc.get("ph_branch"):
		b = _branch_of(doc)
		if b:
			doc.ph_branch = b
	rows = _controlled_rows(doc)
	if not rows or not frappe.db.get_single_value("Pharmacy Settings", "controlled_needs_prescription"):
		return
	if not doc.get("ph_patient_id") and doc.get("customer"):
		doc.ph_patient_id = frappe.db.get_value("Customer", doc.customer, "ph_national_id")
	missing = [lbl for lbl, v in ((_("Prescription No."), doc.get("ph_prescription_no")), (_("Doctor"), doc.get("ph_doctor")), (_("Patient National ID"), doc.get("ph_patient_id"))) if not v]
	if missing:
		frappe.throw(_("Controlled drugs ({0}) need: {1}. Fill them in the Pharmacy section of the invoice.").format(", ".join(r.item_code for r in rows), ", ".join(missing)))


def _batches_of_row(row):
	"""[(batch_no, qty)] of an invoice row, from the batch field or its serial and batch bundle."""
	if row.get("batch_no"):
		return [(row.batch_no, abs(flt(row.stock_qty or row.qty)))]
	bundle = row.get("serial_and_batch_bundle")
	if bundle:
		return [(e.batch_no, abs(flt(e.qty))) for e in frappe.get_all("Serial and Batch Entry", filters={"parent": bundle}, fields=["batch_no", "qty"]) if e.batch_no]
	return [(None, abs(flt(row.stock_qty or row.qty)))]


def invoice_on_submit(doc, method=None):
	if doc.get("is_return"):
		return
	branch = _branch_of(doc)
	for r in _controlled_rows(doc):
		wh = r.get("warehouse") or doc.get("set_warehouse")
		bal = flt(frappe.db.get_value("Bin", {"item_code": r.item_code, "warehouse": wh}, "actual_qty"))
		for batch, qty in _batches_of_row(r):
			frappe.get_doc({
				"doctype": "Controlled Drug Log", "posting_date": doc.posting_date, "branch": branch, "item_code": r.item_code, "item_name": r.item_name, "batch_no": batch,
				"qty": qty, "customer": doc.customer, "patient_id": doc.get("ph_patient_id"), "doctor": doc.get("ph_doctor"), "prescription_no": doc.get("ph_prescription_no"),
				"sales_invoice": doc.name, "balance_after": bal,
			}).insert(ignore_permissions=True)


def invoice_on_cancel(doc, method=None):
	for name in frappe.get_all("Controlled Drug Log", filters={"sales_invoice": doc.name, "cancelled": 0}, pluck="name"):
		frappe.db.set_value("Controlled Drug Log", name, "cancelled", 1)
