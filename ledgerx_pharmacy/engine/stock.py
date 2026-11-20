"""Batch and expiry logic. Pure functions: no database, so every rule is unit tested."""
from datetime import date, timedelta


def days_left(expiry, today):
	"""Days until a batch expires (negative when already expired); None when the batch has no expiry date."""
	if not expiry:
		return None
	return (expiry - today).days


def expiry_status(expiry, today, critical_days=30, near_days=90):
	d = days_left(expiry, today)
	if d is None:
		return "No Expiry"
	if d < 0:
		return "Expired"
	if d <= critical_days:
		return "Critical"
	if d <= near_days:
		return "Near Expiry"
	return "OK"


def fefo_allocate(batches, qty, today, min_days=0):
	"""First-expiry-first-out allocation.

	batches: list of dicts {batch_no, qty, expiry (date or None)}.
	A batch is usable only if it has stock, is not expired and has at least `min_days` left.
	Batches without an expiry date are used last. Returns (allocations, shortfall) where allocations is a
	list of (batch_no, qty). The allocated quantities plus the shortfall always equal the quantity asked for.
	"""
	if qty <= 0:
		return [], 0.0
	usable = []
	for b in batches:
		if (b.get("qty") or 0) <= 0:
			continue
		exp = b.get("expiry")
		if exp is not None and (exp - today).days < max(min_days, 0):
			continue
		usable.append(b)
	usable.sort(key=lambda b: (b.get("expiry") is None, b.get("expiry") or date.max, str(b.get("batch_no"))))
	left = float(qty)
	out = []
	for b in usable:
		if left <= 1e-9:
			break
		take = min(left, float(b["qty"]))
		out.append((b["batch_no"], round(take, 6)))
		left -= take
	return out, round(max(left, 0.0), 6)


def usable_qty(batches, today, min_days=0):
	return round(sum(b["qty"] for b in batches if (b.get("qty") or 0) > 0 and (b.get("expiry") is None or (b["expiry"] - today).days >= max(min_days, 0))), 6)


def expiry_date_for(manufacture, shelf_life_days):
	return manufacture + timedelta(days=int(shelf_life_days)) if manufacture and shelf_life_days else None
