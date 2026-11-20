import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from ledgerx_pharmacy import data
from ledgerx_pharmacy.engine.stock import usable_qty


def execute(filters=None):
	filters = frappe._dict(filters or {})
	ing = filters.active_ingredient
	base_price = None
	if filters.item:
		base = frappe.db.get_value("Item", filters.item, ["ph_active_ingredient", "ph_public_price"], as_dict=1)
		ing = ing or (base and base.ph_active_ingredient)
		base_price = flt(base.ph_public_price) if base else None
	if not ing:
		frappe.throw(_("Choose an item that has an active ingredient, or choose the active ingredient"))
	items = frappe.get_all("Item", filters={"ph_active_ingredient": ing, "disabled": 0}, fields=["name", "item_name", "ph_strength", "ph_form", "ph_public_price", "manufacturer"], order_by="ph_public_price asc")
	branches = data.active_branches([filters.branch] if filters.branch else None)
	whs = data.warehouses_of(branches)
	stock = data.stock_by_item(whs)
	today = getdate(nowdate())
	usable = {}
	for b in data.batch_stock(whs):
		usable.setdefault(b["item_code"], []).append({"qty": b["qty"], "expiry": b["expiry"]})
	rows = []
	for it in items:
		u = usable_qty(usable.get(it.name, []), today)
		if filters.only_in_stock and u <= 0 and stock.get(it.name, 0) <= 0:
			continue
		rows.append({"item_code": it.name, "item_name": it.item_name, "strength": it.ph_strength, "form": it.ph_form, "manufacturer": it.manufacturer, "price": flt(it.ph_public_price),
			"stock": stock.get(it.name, 0.0), "usable": u, "diff": round(flt(it.ph_public_price) - base_price, 2) if base_price is not None else None,
			"this": 1 if it.name == filters.item else 0})
	cols = [
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 200},
		{"label": _("Strength"), "fieldname": "strength", "fieldtype": "Data", "width": 90},
		{"label": _("Form"), "fieldname": "form", "fieldtype": "Data", "width": 90},
		{"label": _("Manufacturer"), "fieldname": "manufacturer", "fieldtype": "Link", "options": "Manufacturer", "width": 130},
		{"label": _("Public Price"), "fieldname": "price", "fieldtype": "Currency", "width": 100},
		{"label": _("Price Difference"), "fieldname": "diff", "fieldtype": "Currency", "width": 110},
		{"label": _("In Stock"), "fieldname": "stock", "fieldtype": "Float", "width": 90},
		{"label": _("Sellable (not expired)"), "fieldname": "usable", "fieldtype": "Float", "width": 130},
	]
	return cols, rows
