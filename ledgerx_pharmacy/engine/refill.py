"""Chronic patients: when is the next refill due."""
from datetime import timedelta


def next_due(last_dispensed, every_days, start=None):
	base = last_dispensed or start
	if not base or not every_days or every_days <= 0:
		return None
	return base + timedelta(days=int(every_days))


def refill_status(due, today, lead_days=3):
	if not due:
		return "Not Started"
	d = (due - today).days
	if d < 0:
		return "Overdue"
	if d <= lead_days:
		return "Due Soon"
	return "Upcoming"
