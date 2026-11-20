"""Database readers shared by the pharmacy documents and reports. Everything here only reads, except the small helpers at the end."""
from collections import defaultdict

import frappe
from frappe.utils import cint, flt, getdate, nowdate, add_days


def settings():
	return frappe.get_cached_doc("Pharmacy Settings")


def branch_doc(name):
	return frappe.get_cached_doc("Pharmacy Branch", name)


def active_branches(only_ids=None):
	filters = {"active": 1}
	if only_ids:
		filters["name"] = ["in", list(only_ids)]
	return frappe.get_all("Pharmacy Branch", filters=filters, fields=["name", "warehouse", "company", "is_central", "expired_warehouse", "cost_center", "price_list"], order_by="branch_name")


def warehouses_of(branches):
	return [b.warehouse for b in branches if b.warehouse]


def item_info(item_code):
	d = frappe.db.get_value("Item", item_code, ["item_name", "stock_uom", "ph_is_drug", "ph_class", "ph_public_price", "has_batch_no", "is_stock_item", "disabled"], as_dict=1)
	if not d:
		frappe.throw(frappe._("Item {0} does not exist").format(item_code))
	d["controlled"] = 1 if d.get("ph_class") == "Controlled" else 0
	return d


def conversion_factor(item_code, uom):
	stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
	if not uom or uom == stock_uom:
		return 1.0
	cf = frappe.db.get_value("UOM Conversion Detail", {"parent": item_code, "uom": uom}, "conversion_factor")
	if not cf:
		frappe.throw(frappe._("Item {0} has no conversion from {1} to {2}").format(item_code, uom, stock_uom))
	return flt(cf)


def public_price(item_code, branch=None, uom=None):
	"""Official public price for one sales unit. Item Price in the branch (or public) price list first, then the price typed on the item."""
	s = settings()
	pl = (branch_doc(branch).price_list if branch else None) or s.public_price_list
	price = None
	if pl:
		price = frappe.db.get_value("Item Price", {"item_code": item_code, "price_list": pl, "selling": 1, "uom": uom or frappe.db.get_value("Item", item_code, "stock_uom")}, "price_list_rate")
		if price is None and uom:
			base = frappe.db.get_value("Item Price", {"item_code": item_code, "price_list": pl, "selling": 1, "uom": frappe.db.get_value("Item", item_code, "stock_uom")}, "price_list_rate")
			if base is not None:
				price = flt(base) * conversion_factor(item_code, uom)
	if price is None:
		base = frappe.db.get_value("Item", item_code, "ph_public_price")
		if base:
			price = flt(base) * (conversion_factor(item_code, uom) if uom else 1)
	return flt(price)


BATCH_SQL = """
	SELECT sbe.batch_no AS batch_no, sbe.warehouse AS warehouse, b.item AS item_code, b.expiry_date AS expiry, SUM(sbe.qty) AS qty
	FROM `tabSerial and Batch Entry` sbe
	INNER JOIN `tabStock Ledger Entry` sle ON sle.serial_and_batch_bundle = sbe.parent
	INNER JOIN `tabBatch` b ON b.name = sbe.batch_no
	WHERE sle.is_cancelled = 0 {where}
	GROUP BY sbe.batch_no, sbe.warehouse
	HAVING SUM(sbe.qty) > 0.000001
"""


def batch_stock(warehouses, item_code=None):
	"""Batch quantities per warehouse (expired batches included). Returns list of dicts {batch_no, warehouse, item_code, expiry, qty}."""
	warehouses = [w for w in (warehouses or []) if w]
	if not warehouses:
		return []
	where, vals = "AND sbe.warehouse IN %(wh)s", {"wh": tuple(warehouses)}
	if item_code:
		where += " AND b.item = %(item)s"
		vals["item"] = item_code
	rows = frappe.db.sql(BATCH_SQL.format(where=where), vals, as_dict=1)
	for r in rows:
		r["expiry"] = getdate(r["expiry"]) if r.get("expiry") else None
		r["qty"] = flt(r["qty"])
	return rows


def fefo(item_code, warehouse, stock_qty, today=None, min_days=None):
	"""Allocate stock_qty of an item from a warehouse, expiring batches first. Returns (allocations, shortfall)."""
	from .engine.stock import fefo_allocate

	today = getdate(today or nowdate())
	if min_days is None:
		min_days = cint(settings().min_days_to_sell)
	if not cint(frappe.db.get_value("Item", item_code, "has_batch_no")):
		have = flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty"))
		take = min(have, stock_qty)
		return ([(None, take)] if take > 0 else []), max(stock_qty - take, 0)
	rows = [{"batch_no": r["batch_no"], "qty": r["qty"], "expiry": r["expiry"]} for r in batch_stock([warehouse], item_code)]
	return fefo_allocate(rows, stock_qty, today, min_days)


def stock_by_item(warehouses):
	warehouses = [w for w in warehouses if w]
	if not warehouses:
		return {}
	out = defaultdict(float)
	for r in frappe.db.sql("SELECT item_code, SUM(actual_qty) q FROM `tabBin` WHERE warehouse IN %(w)s GROUP BY item_code", {"w": tuple(warehouses)}, as_dict=1):
		out[r.item_code] = flt(r.q)
	return out


def on_order_by_item(warehouses):
	warehouses = [w for w in warehouses if w]
	if not warehouses:
		return {}
	out = defaultdict(float)
	for r in frappe.db.sql("SELECT item_code, SUM(ordered_qty) q FROM `tabBin` WHERE warehouse IN %(w)s GROUP BY item_code", {"w": tuple(warehouses)}, as_dict=1):
		out[r.item_code] = flt(r.q)
	return out


def daily_sales(warehouses, days):
	"""Average quantity sold per day (in stock units) from submitted sales invoices that took stock from these warehouses. Returns are subtracted."""
	warehouses = [w for w in warehouses if w]
	days = max(cint(days), 1)
	if not warehouses:
		return {}
	rows = frappe.db.sql(
		"""SELECT sii.item_code, SUM(sii.stock_qty) q FROM `tabSales Invoice Item` sii INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE si.docstatus = 1 AND si.update_stock = 1 AND sii.warehouse IN %(w)s AND si.posting_date >= %(d)s GROUP BY sii.item_code""",
		{"w": tuple(warehouses), "d": add_days(nowdate(), -days)}, as_dict=1)
	return {r.item_code: max(flt(r.q), 0) / days for r in rows}


def reorder_levels(warehouses):
	"""{item: (min_level, reorder_qty)} summed over the given warehouses from the item reorder table."""
	warehouses = [w for w in warehouses if w]
	if not warehouses:
		return {}
	out = defaultdict(lambda: [0.0, 0.0])
	for r in frappe.db.sql("SELECT parent item_code, warehouse_reorder_level lv, warehouse_reorder_qty q FROM `tabItem Reorder` WHERE warehouse IN %(w)s", {"w": tuple(warehouses)}, as_dict=1):
		out[r.item_code][0] += flt(r.lv)
		out[r.item_code][1] += flt(r.q)
	return {k: tuple(v) for k, v in out.items()}


def pack_size(item_code):
	"""Purchase pack in stock units: the conversion factor of the item's purchase unit, 1 when it has none."""
	d = frappe.db.get_value("Item", item_code, ["stock_uom", "purchase_uom"], as_dict=1)
	if d and d.purchase_uom and d.purchase_uom != d.stock_uom:
		cf = frappe.db.get_value("UOM Conversion Detail", {"parent": item_code, "uom": d.purchase_uom}, "conversion_factor")
		if cf and cf > 0:
			return float(cf)
	return 1.0


def supplier_for(item_code):
	"""Default supplier of an item, else the supplier of the last purchase order."""
	s = frappe.db.get_value("Item Default", {"parent": item_code}, "default_supplier")
	if s:
		return s
	s = frappe.db.get_value("Item Supplier", {"parent": item_code}, "supplier")
	if s:
		return s
	r = frappe.db.sql("SELECT po.supplier FROM `tabPurchase Order Item` poi INNER JOIN `tabPurchase Order` po ON po.name = poi.parent WHERE poi.item_code = %s AND po.docstatus = 1 ORDER BY po.transaction_date DESC LIMIT 1", item_code)
	return r[0][0] if r else None


def last_purchase_rate(item_code):
	return flt(frappe.db.get_value("Item", item_code, "last_purchase_rate"))


def offers_for(item_code, today=None):
	today = getdate(today or nowdate())
	rows = frappe.get_all("Supplier Offer", filters={"item_code": item_code, "active": 1}, fields=["name", "supplier", "price", "discount_pct", "min_qty", "bonus_per", "bonus_qty", "valid_from", "valid_to", "payment_days"])
	for r in rows:
		r["valid_from"] = getdate(r["valid_from"]) if r.get("valid_from") else None
		r["valid_to"] = getdate(r["valid_to"]) if r.get("valid_to") else None
	return rows
