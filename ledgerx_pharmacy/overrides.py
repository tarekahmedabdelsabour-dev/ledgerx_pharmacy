"""Shows the pharmacy documents in the "Connections" panel of the records they belong to."""
from frappe import _


def _group(data, label, items, fields=None):
	data.setdefault("transactions", [])
	data["transactions"].append({"label": _(label), "items": items})
	if fields:
		data.setdefault("non_standard_fieldnames", {}).update(fields)
	return data


def customer(data=None):
	return _group(data or {}, "Pharmacy", ["Pharmacy Dispense", "Refill Plan"])


def item(data=None):
	return _group(data or {}, "Pharmacy", ["Supplier Offer", "Refill Plan", "Controlled Drug Log"])


def supplier(data=None):
	return _group(data or {}, "Pharmacy", ["Supplier Offer"])


def sales_invoice(data=None):
	return _group(data or {}, "Pharmacy", ["Pharmacy Dispense", "Controlled Drug Log"], {"Pharmacy Dispense": "sales_invoice"})


def warehouse(data=None):
	return _group(data or {}, "Pharmacy", ["Pharmacy Branch"], {"Pharmacy Branch": "warehouse"})


def employee(data=None):
	return _group(data or {}, "Pharmacy", ["Pharmacy Branch"], {"Pharmacy Branch": "manager"})
