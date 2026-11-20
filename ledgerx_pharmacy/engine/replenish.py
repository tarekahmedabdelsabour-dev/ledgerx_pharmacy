"""Purchasing: how much to order, and which supplier offer is really the cheapest."""
import math
from datetime import date


def order_qty(stock, on_order, daily_sales, cover_days, min_level=0.0, max_level=0.0, pack=1.0):
	"""Quantity to order now. Target stock = what sells in `cover_days` (or the max level when it is larger), never below the
	minimum level. The order is rounded UP to whole packs. Returns 0 when the stock plus orders already reach the target
	and the stock is not below the minimum level."""
	pack = float(pack) if pack and pack > 0 else 1.0
	target = max(float(daily_sales) * float(cover_days), float(max_level or 0), float(min_level or 0))
	position = float(stock) + float(on_order)
	if position >= target - 1e-9:
		return 0.0
	if position >= float(min_level or 0) and daily_sales <= 0:
		return 0.0
	need = target - position
	return float(math.ceil(need / pack - 1e-9) * pack)


def effective_cost(offer, qty, base_price, today=None):
	"""Cost per unit received, counting the offer's discount and the free bonus units. None when the offer cannot apply.

	offer: dict(price, discount_pct, min_qty, bonus_qty, bonus_per, valid_from, valid_to). price 0/None = use base_price.
	Buying `qty` units pays for qty and receives qty + bonus units, bonus = floor(qty / bonus_per) * bonus_qty.
	"""
	today = today or date.today()
	if offer.get("valid_from") and today < offer["valid_from"]:
		return None
	if offer.get("valid_to") and today > offer["valid_to"]:
		return None
	if qty < (offer.get("min_qty") or 0):
		return None
	price = offer.get("price") or base_price
	if not price or price <= 0:
		return None
	unit = price * (1 - min(max(offer.get("discount_pct") or 0, 0), 100) / 100.0)
	bonus = 0.0
	if offer.get("bonus_per") and offer.get("bonus_qty"):
		bonus = math.floor(qty / offer["bonus_per"]) * offer["bonus_qty"]
	return round(unit * qty / (qty + bonus), 6), bonus


def best_offer(offers, qty, base_price, today=None):
	"""Cheapest effective cost across the supplier offers. Ties go to the supplier named first alphabetically so the
	choice is repeatable. Returns dict(supplier, cost, bonus, offer) or None."""
	best = None
	for o in offers:
		r = effective_cost(o, qty, base_price, today)
		if r is None:
			continue
		cost, bonus = r
		key = (cost, str(o.get("supplier")))
		if best is None or key < best[0]:
			best = (key, {"supplier": o.get("supplier"), "cost": cost, "bonus": bonus, "offer": o.get("name")})
	return best[1] if best else None


def paid_units(qty, offer):
	"""Units to pay for when the wish is to RECEIVE at least `qty` units with the bonus counted (never over-buys by more than a pack of bonus)."""
	if not (offer.get("bonus_per") and offer.get("bonus_qty")):
		return qty
	per, free = offer["bonus_per"], offer["bonus_qty"]
	n = 0
	while n + math.floor(n / per) * free < qty:
		n += 1
	return n
