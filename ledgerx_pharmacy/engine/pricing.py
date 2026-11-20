"""Prices, discounts and the split of a bill between the patient and the insurance company."""


def r2(x):
	return round(float(x) + 1e-9, 2) if x >= 0 else round(float(x) - 1e-9, 2)


def line_amount(price, qty, discount_pct=0.0):
	"""Net amount of one line. The discount is a percentage of the official public price."""
	d = min(max(float(discount_pct or 0), 0.0), 100.0)
	return r2(float(price) * float(qty) * (1 - d / 100.0))


def split_insurance(lines, cover_pct, patient_cap=0.0, min_copay=0.0, exclude_cosmetics=False):
	"""Split a bill. lines: list of dicts {amount, covered(bool, default True), klass(optional)}.

	Only covered lines are shared with the insurer; the insurer pays cover_pct of them. Then:
	- patient_cap > 0: the patient never pays more than this on the covered part (the insurer pays the rest);
	- min_copay: the patient pays at least this much on the covered part (never more than the covered total).
	Returns dict(gross, covered, uncovered, insurer, patient) and insurer + patient == gross exactly (to 2 decimals).
	"""
	gross = r2(sum(l["amount"] for l in lines))
	covered = 0.0
	for l in lines:
		ok = l.get("covered", True)
		if exclude_cosmetics and l.get("klass") in ("Cosmetic", "Supplement"):
			ok = False
		if ok:
			covered += l["amount"]
	covered = r2(covered)
	uncovered = r2(gross - covered)
	pct = min(max(float(cover_pct or 0), 0.0), 100.0)
	insurer = r2(covered * pct / 100.0)
	patient_covered = r2(covered - insurer)
	if patient_cap and patient_cap > 0 and patient_covered > patient_cap:
		patient_covered = r2(patient_cap)
	if min_copay and min_copay > 0 and patient_covered < min_copay:
		patient_covered = r2(min(min_copay, covered))
	insurer = r2(covered - patient_covered)
	patient = r2(gross - insurer)
	return {"gross": gross, "covered": covered, "uncovered": uncovered, "insurer": insurer, "patient": patient}
