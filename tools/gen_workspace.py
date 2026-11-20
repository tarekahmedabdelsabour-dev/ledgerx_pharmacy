"""Writes the workspace, sidebar and dock JSON of ledgerx_pharmacy. Run from the repo root."""
import json
import os
import uuid

BASE = os.path.join(os.path.dirname(__file__), "..", "ledgerx_pharmacy")
TS = "2026-11-21 09:00:00.000000"  # raise this whenever the workspace changes: migrate only re-reads a file that is newer than the saved one
TODAY = [["Pharmacy Dispense", "docstatus", "=", 1], ["Pharmacy Dispense", "posting_date", "Timespan", "today"]]
CARDS = [
	("Sales Today", "Pharmacy Dispense", TODAY, "Count", None),
	("Refills Overdue", "Refill Plan", [["Refill Plan", "status", "=", "Overdue"]], "Count", None),
	("Refills Due Soon", "Refill Plan", [["Refill Plan", "status", "=", "Due Soon"]], "Count", None),
	("Transfers to Submit", "Pharmacy Transfer", [["Pharmacy Transfer", "docstatus", "=", 0]], "Count", None),
	("Purchase Plans to Order", "Pharmacy Purchase Plan", [["Pharmacy Purchase Plan", "status", "=", "Loaded"]], "Count", None),
	("Controlled Drug Entries This Month", "Controlled Drug Log", [["Controlled Drug Log", "posting_date", "Timespan", "this month"], ["Controlled Drug Log", "cancelled", "=", 0]], "Count", None),
]
CHARTS = [
	("Sales by Branch", "Pharmacy Dispense", "Donut", "group", {"by": "branch", "filters": [["Pharmacy Dispense", "docstatus", "=", 1]]}),
	("Refill Plans by Status", "Refill Plan", "Donut", "group", {"by": "status"}),
]
GROUPS = [
	("Daily Work", None, 0, [
		("Pharmacy Dispense", "DocType", "Pharmacy Dispense", "plus-square"), ("Pharmacy Transfer", "DocType", "Pharmacy Transfer", "arrow-left-right"),
		("Refill Plan", "DocType", "Refill Plan", "refresh-cw")]),
	("Purchasing", "shopping-cart", 0, [
		("Pharmacy Purchase Plan", "DocType", "Pharmacy Purchase Plan", "list-checks"), ("Supplier Offer", "DocType", "Supplier Offer", "percent"),
		("Purchase Order", "DocType", "Purchase Order", "shopping-cart"), ("Purchase Receipt", "DocType", "Purchase Receipt", "package-check")]),
	("Insurance", "shield", 0, [
		("Insurance Company", "DocType", "Insurance Company", "building"), ("Insurance Plan", "DocType", "Insurance Plan", "id-card")]),
	("Reports", "bar-chart-3", 0, [
		("Expiry Report", "Report", "Expiry Report", "hourglass"), ("Drug Alternatives", "Report", "Drug Alternatives", "replace"),
		("Branch Performance", "Report", "Branch Performance", "bar-chart-3"), ("Controlled Drug Register", "Report", "Controlled Drug Register", "lock"),
		("Insurance Receivable", "Report", "Insurance Receivable", "banknote"), ("Refills Due", "Report", "Refills Due", "bell"),
		("Controlled Drug Log", "DocType", "Controlled Drug Log", "lock")]),
	("Setup", "settings", 0, [
		("Pharmacy Branch", "DocType", "Pharmacy Branch", "hospital"), ("Pharmacy Settings", "DocType", "Pharmacy Settings", "settings"),
		("Active Ingredient", "DocType", "Active Ingredient", "flask-conical")]),
	("Source Data", "database", 1, [
		("Item", "DocType", "Item", "box"), ("Batch", "DocType", "Batch", "boxes"), ("Customer", "DocType", "Customer", "users"), ("Supplier", "DocType", "Supplier", "truck"),
		("Warehouse", "DocType", "Warehouse", "warehouse"), ("Stock Entry", "DocType", "Stock Entry", "package"), ("Sales Invoice", "DocType", "Sales Invoice", "file-text"),
		("Price List", "DocType", "Price List", "tag")]),
]
TOP = ["Pharmacy Dispense", "Pharmacy Transfer", "Pharmacy Purchase Plan", "Refill Plan"]


def write(path, data):
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w", encoding="utf-8") as fh:
		json.dump(data, fh, indent=1, ensure_ascii=False)
		fh.write("\n")


def slug(n):
	return n.lower().replace(" ", "_").replace("-", "_")


def write_cards():
	for label, dt, flt, fn, _f in CARDS:
		write(os.path.join(BASE, "pharmacy", "number_card", slug(label), slug(label) + ".json"), {
			"creation": TS, "docstatus": 0, "doctype": "Number Card", "document_type": dt, "filters_json": json.dumps(flt), "function": fn,
			"idx": 0, "is_public": 1, "is_standard": 1, "label": label, "modified": TS, "modified_by": "Administrator", "module": "Pharmacy",
			"name": label, "owner": "Administrator", "show_percentage_stats": 0, "stats_time_interval": "Daily", "type": "Document Type"})
	for name, dt, typ, kind, x in CHARTS:
		d = {"chart_name": name, "creation": TS, "docstatus": 0, "doctype": "Dashboard Chart", "document_type": dt, "dynamic_filters_json": "",
			"idx": 0, "is_public": 1, "is_standard": 1, "modified": TS, "modified_by": "Administrator", "module": "Pharmacy", "name": name,
			"number_of_groups": 0, "owner": "Administrator", "type": typ, "use_report_chart": 0, "y_axis": []}
		if kind == "group":
			d.update({"chart_type": "Group By", "group_by_based_on": x["by"], "group_by_type": "Count", "filters_json": json.dumps(x.get("filters", [])), "timeseries": 0})
		else:
			d.update({"chart_type": "Count", "based_on": x["based_on"], "filters_json": json.dumps(x["filters"]), "time_interval": x.get("interval", "Monthly"),
				"timeseries": 1, "timespan": x.get("timespan", "Last Year")})
		write(os.path.join(BASE, "pharmacy", "dashboard_chart", slug(name), slug(name) + ".json"), d)


def main():
	write_cards()
	rid = lambda: uuid.uuid4().hex[:10]
	content = [{"id": rid(), "type": "header", "data": {"text": '<span class="h4"><b>Pharmacy</b></span>', "col": 12}}]
	for label, *_r in CARDS:
		content.append({"id": rid(), "type": "number_card", "data": {"number_card_name": label, "col": 3}})
	for name, *_r in CHARTS:
		content.append({"id": rid(), "type": "chart", "data": {"chart_name": name, "col": 6}})
	shortcuts, links = [], []
	for label in TOP:
		content.insert(1 + len(shortcuts), {"id": rid(), "type": "shortcut", "data": {"shortcut_name": label, "col": 3}})
		kind = "DocType"
		sc = {"label": label, "link_to": label, "type": kind}
		if kind == "DocType":
			sc["doc_view"] = "List"
		else:
			sc["is_query_report"] = 1
		shortcuts.append(sc)
	for title, _i, _c, items in GROUPS:
		content.append({"id": rid(), "type": "card", "data": {"card_name": title, "col": 4}})
		links.append({"type": "Card Break", "label": title, "hidden": 0, "is_query_report": 0, "link_count": len(items), "onboard": 0})
		for label, kind, target, _icon in items:
			links.append({"type": "Link", "label": label, "link_type": kind, "link_to": target, "hidden": 0, "is_query_report": 1 if kind == "Report" else 0,
				"onboard": 0, "dependencies": "", "only_for": ""})
	write(os.path.join(BASE, "pharmacy", "workspace", "pharmacy", "pharmacy.json"), {
		"charts": [{"chart_name": c[0], "label": c[0]} for c in CHARTS], "content": json.dumps(content), "creation": TS, "custom_blocks": [], "docstatus": 0, "doctype": "Workspace",
		"for_user": "", "hide_custom": 1, "icon": "pill", "idx": 1, "is_hidden": 0, "label": "Pharmacy", "links": links, "title": "Pharmacy", "modified": TS,
		"modified_by": "Administrator", "module": "Pharmacy", "name": "Pharmacy", "number_cards": [{"label": c[0], "number_card_name": c[0]} for c in CARDS], "owner": "Administrator",
		"parent_page": "", "public": 1, "quick_lists": [], "roles": [], "sequence_id": 31.0, "shortcuts": shortcuts})
	def row(i, label, kind, target, icon, child):
		d = {"child": child, "collapsible": 1, "doctype": "Sidebar Item", "icon": icon, "idx": i, "indent": 0, "keep_closed": 0, "label": label,
			"parentfield": "items", "parenttype": "Sidebar", "show_arrow": 0, "type": "Link"}
		if kind == "URL":
			d.update({"link_type": "URL", "url": target, "open_in_new_tab": 1})
		else:
			d.update({"link_to": target, "link_type": kind})
		return d
	items = [row(1, "Home", "Workspace", "Pharmacy", "house", 0)]
	for title, icon, closed, entries in GROUPS:
		if icon:
			items.append({"child": 0, "collapsible": 1, "doctype": "Sidebar Item", "icon": icon, "idx": len(items) + 1, "indent": 1, "keep_closed": closed,
				"label": title, "link_type": "DocType", "parentfield": "items", "parenttype": "Sidebar", "show_arrow": 0, "type": "Section Break"})
		for label, kind, target, ic in entries:
			items.append(row(len(items) + 1, label, kind, target, ic, 1 if icon else 0))
	write(os.path.join(BASE, "sidebar", "pharmacy", "pharmacy.json"), {"app": "ledgerx_pharmacy", "doctype": "Sidebar", "header_icon": "pill",
		"items": items, "module": "Pharmacy", "name": "Pharmacy", "standard": 1, "title": "Pharmacy"})
	write(os.path.join(BASE, "dock", "pharmacy", "pharmacy.json"), {"app": "ledgerx_pharmacy", "creation": TS, "docstatus": 0, "doctype": "Dock", "idx": 0,
		"items": [{"added": 0, "hidden": 0, "icon": "pill", "link_to": "Pharmacy", "link_type": "Sidebar", "title": "Pharmacy"}],
		"modified": TS, "modified_by": "Administrator", "name": "pharmacy", "owner": "Administrator", "standard": 1})


main()
