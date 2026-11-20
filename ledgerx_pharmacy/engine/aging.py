"""Receivable aging for insurance companies: payments settle the oldest bills first."""
from datetime import date


def fifo_aging(debits, credits_total, as_of, edges=(30, 60, 90)):
	"""debits: list of (date, amount) bills; credits_total: everything paid or credited so far.
	Payments are applied to the oldest bills first. Returns dict(total, buckets=[...]) where the buckets hold what is still
	owed by age: 0-30, 31-60, 61-90, over 90 (for the default edges). A surplus of credits (insurer paid in advance) is returned
	as a negative `unapplied`, not hidden inside the buckets."""
	left = float(credits_total)
	buckets = [0.0] * (len(edges) + 1)
	for d, amt in sorted(debits, key=lambda x: x[0]):
		amt = float(amt)
		if amt <= 0:
			continue
		used = min(left, amt)
		left -= used
		rest = amt - used
		if rest <= 1e-9:
			continue
		age = (as_of - d).days
		i = 0
		while i < len(edges) and age > edges[i]:
			i += 1
		buckets[i] += rest
	total = round(sum(buckets), 2)
	return {"total": total, "buckets": [round(b, 2) for b in buckets], "unapplied": round(-left, 2) if left > 1e-9 else 0.0}
