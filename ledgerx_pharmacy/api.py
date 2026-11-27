"""Small whitelisted helpers for the pharmacy screens."""
import json

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from . import data
from .engine.pricing import line_amount, split_insurance
from .engine.stock import days_left, expiry_status, usable_qty


@frappe.whitelist()
def item_details(item_code, branch, uom=None):
	"""Price, unit, sellable stock and nearest expiry of an item at a branch: what the cashier needs after picking an item."""
	frappe.has_permission("Pharmacy Dispense", "create", throw=True)
	info = data.item_info(item_code)
	uom = uom or info.stock_uom
	cf = data.conversion_factor(item_code, uom)
	wh = data.branch_doc(branch).warehouse
	s = data.settings()
	today = getdate(nowdate())
	rows = [{"qty": b["qty"], "expiry": b["expiry"]} for b in data.batch_stock([wh], item_code)] if cint(frappe.db.get_value("Item", item_code, "has_batch_no")) else None
	if rows is None:
		sellable = flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": wh}, "actual_qty"))
		nearest = None
	else:
		sellable = usable_qty(rows, today, cint(s.min_days_to_sell))
		dated = sorted(r["expiry"] for r in rows if r["expiry"] and r["expiry"] >= today and r["qty"] > 0)
		nearest = dated[0] if dated else None
	return {
		"item_name": info.item_name, "uom": uom, "conversion_factor": cf, "price": data.public_price(item_code, branch, uom), "klass": info.ph_class, "is_controlled": info.controlled,
		"sellable": flt(sellable / cf, 3), "nearest_expiry": nearest, "days_left": days_left(nearest, today) if nearest else None,
		"status": expiry_status(nearest, today, cint(s.critical_expiry_days), cint(s.near_expiry_days)) if nearest else None,
	}


@frappe.whitelist()
def item_by_barcode(code):
	"""Item for a scanned barcode (Item Barcode, item code or item name)."""
	frappe.has_permission("Pharmacy Dispense", "create", throw=True)
	code = (code or "").strip()
	if not code:
		return None
	return frappe.db.get_value("Item Barcode", {"barcode": code}, "parent") or (code if frappe.db.exists("Item", code) else None)


@frappe.whitelist()
def split_preview(items, plan=None):
	"""What the patient and the insurer will each pay: the same arithmetic the submitted sale uses."""
	frappe.has_permission("Pharmacy Dispense", "create", throw=True)
	items = json.loads(items) if isinstance(items, str) else items
	lines = []
	for r in items:
		amount = line_amount(flt(r.get("price")), flt(r.get("qty")), flt(r.get("discount_pct")))
		covered = bool(cint(r.get("covered", 1)))
		lines.append({"amount": amount, "covered": covered, "klass": r.get("klass")})
	if not plan:
		return split_insurance([{"amount": l["amount"], "covered": False} for l in lines], 0)
	p = frappe.get_cached_doc("Insurance Plan", plan)
	for l in lines:
		if p.exclude_cosmetics and l.get("klass") in ("Cosmetic", "Supplement"):
			l["covered"] = False
	return split_insurance(lines, p.cover_pct, p.patient_cap, p.min_copay, False)
