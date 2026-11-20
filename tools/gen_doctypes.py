"""Builds every DocType JSON of ledgerx_pharmacy from the compact table below.
Run from the repo root:  python3 tools/gen_doctypes.py   (rewrites ledgerx_pharmacy/pharmacy/doctype/*/*.json; controller .py files are never overwritten)"""
import json
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..", "ledgerx_pharmacy", "pharmacy", "doctype")
TS = "2026-11-21 08:00:00.000000"
MODULE = "Pharmacy"
MGR, PH, ASST, BUY = "Pharmacy Manager", "Pharmacist", "Pharmacy Assistant", "Pharmacy Buyer"


def f(name, ftype, label=None, **kw):
	d = {"fieldname": name, "fieldtype": ftype}
	if ftype not in ("Section Break", "Column Break", "Tab Break"):
		d["label"] = label or name.replace("_", " ").title()
	elif label:
		d["label"] = label
	d.update(kw)
	return d


def sec(name, label=None, **kw):
	return f(name, "Section Break", label, **kw)


def col(name):
	return f(name, "Column Break")


def perms(*rows):
	"""mode: r | rw | rwc | all | sub (rwc + submit) | full (all + submit/cancel/amend)"""
	out = []
	for role, mode in rows:
		p = {"role": role, "read": 1, "report": 1, "print": 1, "export": 1}
		if mode in ("rw", "rwc", "all", "sub", "full"):
			p["write"] = 1
		if mode in ("rwc", "all", "sub", "full"):
			p["create"] = 1
		if mode in ("all", "full"):
			p["delete"] = 1
		if mode in ("sub", "full"):
			p["submit"] = 1
		if mode == "full":
			p.update({"cancel": 1, "amend": 1})
		out.append(p)
	out.append({"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "print": 1, "export": 1})
	return out


DT = {}


def doctype(name, fields, **kw):
	DT[name] = {"name": name, "fields": fields, **kw}


READ_ALL = [(MGR, "r"), (PH, "r"), (ASST, "r"), (BUY, "r")]

# ------------------------------------------------------------------ settings
doctype("Pharmacy Settings", [
	f("company", "Link", "Company", options="Company"),
	f("public_price_list", "Link", "Public Price List", options="Price List", description="Official public prices live here. The price typed on an item is kept in this list."),
	f("walk_in_customer", "Link", "Walk-in Customer", options="Customer", description="Used when a sale has no patient."),
	f("sales_taxes_template", "Link", "Sales Taxes Template", options="Sales Taxes and Charges Template", description="Leave empty when medicines are exempt."),
	sec("sb_exp", "Expiry"),
	f("critical_expiry_days", "Int", "Critical Expiry (days)", default=30),
	f("near_expiry_days", "Int", "Near Expiry (days)", default=90),
	f("min_days_to_sell", "Int", "Do Not Sell With Fewer Days Left Than", default=0, description="0 = only expired batches are blocked."),
	sec("sb_ctrl", "Controlled Drugs"),
	f("controlled_needs_prescription", "Check", "Controlled Drugs Need a Prescription Number, Doctor and Patient ID", default=1),
	sec("sb_buy", "Purchasing"),
	f("cover_days", "Int", "Days of Sales to Keep in Stock", default=14),
	f("sales_lookback_days", "Int", "Days of Sales History to Use", default=60),
	sec("sb_ref", "Chronic Patients"),
	f("refill_lead_days", "Int", "Remind This Many Days Before a Refill Is Due", default=3),
], issingle=1, icon="fa fa-medkit", perms=perms((MGR, "rw"), (PH, "r"), (BUY, "r")))

# ------------------------------------------------------------------ master data
doctype("Active Ingredient", [
	f("ingredient_name", "Data", "Active Ingredient", reqd=1, unique=1, in_list_view=1),
	f("notes", "Small Text", "Notes"),
], autoname="field:ingredient_name", icon="fa fa-flask", search_fields="ingredient_name", perms=perms((MGR, "all"), (PH, "rwc"), (BUY, "rwc"), (ASST, "r")))

doctype("Pharmacy Branch", [
	f("branch_name", "Data", "Branch Name", reqd=1, unique=1, in_list_view=1),
	f("company", "Link", "Company", options="Company", reqd=1),
	f("is_central", "Check", "Central Store", in_list_view=1, description="The main store that supplies the other branches."),
	f("active", "Check", "Active", default=1, in_list_view=1),
	col("cb1"),
	f("warehouse", "Link", "Stock Warehouse", options="Warehouse", reqd=1, in_list_view=1, description="Where this branch keeps sellable stock."),
	f("expired_warehouse", "Link", "Expired / Quarantine Warehouse", options="Warehouse", description="Where expired or damaged stock is moved."),
	f("cost_center", "Link", "Cost Center", options="Cost Center"),
	f("price_list", "Link", "Price List Override", options="Price List", description="Leave empty to use the public price list."),
	sec("sb_lic", "License and Contact"),
	f("license_no", "Data", "Pharmacy License No."),
	f("license_expiry", "Date", "License Valid Until"),
	f("manager", "Link", "Branch Manager", options="Employee"),
	f("manager_user", "Data", "Manager User", read_only=1, fetch_from="manager.user_id"),
	col("cb2"),
	f("phone", "Data", "Phone"),
	f("address", "Small Text", "Address"),
], autoname="field:branch_name", title_field="branch_name", icon="fa fa-hospital-o", search_fields="branch_name",
	perms=perms((MGR, "all"), (PH, "r"), (ASST, "r"), (BUY, "r")))

doctype("Insurance Company", [
	f("company_name", "Data", "Insurance Company", reqd=1, unique=1, in_list_view=1),
	f("customer", "Link", "Customer Account", options="Customer", reqd=1, description="The customer that carries what this insurer owes us. Created automatically when left empty."),
	f("active", "Check", "Active", default=1, in_list_view=1),
	f("payment_days", "Int", "Usual Payment Days", default=60),
	f("contact", "Small Text", "Contact"),
], autoname="field:company_name", icon="fa fa-shield", perms=perms((MGR, "all"), (PH, "rwc"), (ASST, "r"), (BUY, "r")))

doctype("Insurance Plan", [
	f("insurance_company", "Link", "Insurance Company", options="Insurance Company", reqd=1, in_list_view=1, in_standard_filter=1),
	f("plan_name", "Data", "Plan Name", reqd=1, in_list_view=1),
	f("cover_pct", "Percent", "Insurer Pays %", reqd=1, default=80, in_list_view=1),
	f("patient_cap", "Currency", "Most the Patient Pays per Visit", description="0 = no cap."),
	f("min_copay", "Currency", "Least the Patient Pays per Visit", description="A flat fee taken from every covered visit."),
	f("exclude_cosmetics", "Check", "Cosmetics and Supplements Not Covered", default=1),
	f("valid_to", "Date", "Valid Until"),
	f("active", "Check", "Active", default=1, in_list_view=1),
], autoname="format:{insurance_company}-{plan_name}", title_field="plan_name", icon="fa fa-id-card-o", perms=perms((MGR, "all"), (PH, "rwc"), (ASST, "r"), (BUY, "r")))

# ------------------------------------------------------------------ dispensing
doctype("Dispense Item", [
	f("item_code", "Link", "Item", options="Item", reqd=1, in_list_view=1),
	f("item_name", "Data", "Item Name", read_only=1, in_list_view=1),
	f("uom", "Link", "Unit", options="UOM", in_list_view=1),
	f("conversion_factor", "Float", "Units in Stock Unit", default=1, read_only=1),
	f("qty", "Float", "Quantity", reqd=1, default=1, in_list_view=1),
	f("price", "Currency", "Public Price", in_list_view=1),
	f("discount_pct", "Percent", "Discount %"),
	f("amount", "Currency", "Amount", read_only=1, in_list_view=1),
	f("covered", "Check", "Covered by Insurance", default=1),
	f("klass", "Data", "Class", read_only=1),
	f("is_controlled", "Check", "Controlled", read_only=1),
	f("batches", "Small Text", "Batches Used", read_only=1, description="Chosen by first-expiry-first-out when the sale is submitted."),
], istable=1)

doctype("Pharmacy Dispense", [
	f("branch", "Link", "Branch", options="Pharmacy Branch", reqd=1, in_list_view=1, in_standard_filter=1),
	f("posting_date", "Date", "Date", reqd=1, default="Today", in_list_view=1),
	f("customer", "Link", "Patient / Customer", options="Customer", in_standard_filter=1, in_list_view=1),
	f("patient_id", "Data", "Patient National ID", fetch_from="customer.ph_national_id", fetch_if_empty=1),
	col("cb1"),
	f("insurance_plan", "Link", "Insurance Plan", options="Insurance Plan", in_standard_filter=1),
	f("member_no", "Data", "Member No."),
	f("approval_no", "Data", "Approval No."),
	sec("sb_rx", "Prescription"),
	f("prescription_no", "Data", "Prescription No."),
	col("cb2"),
	f("doctor", "Data", "Doctor"),
	sec("sb_items", "Items"),
	f("scan_barcode", "Data", "Scan Barcode", no_copy=1, description="Scan the pack to add the item."),
	f("items", "Table", "Items", options="Dispense Item", reqd=1),
	sec("sb_tot", "Totals"),
	f("gross_total", "Currency", "Total", read_only=1, in_list_view=1),
	f("insurer_share", "Currency", "Insurer Pays", read_only=1),
	f("patient_share", "Currency", "Patient Pays", read_only=1),
	col("cb3"),
	f("mode_of_payment", "Link", "Payment Method", options="Mode of Payment", default="Cash"),
	f("amount_received", "Currency", "Patient Paid Now", description="Leave empty to take the whole patient share."),
	sec("sb_links", "Accounting"),
	f("sales_invoice", "Link", "Sales Invoice", options="Sales Invoice", read_only=1),
	f("payment_entry", "Link", "Payment Entry", options="Payment Entry", read_only=1),
	f("insurer_entry", "Link", "Insurer Journal Entry", options="Journal Entry", read_only=1),
	f("company", "Link", "Company", options="Company", read_only=1, fetch_from="branch.company"),
	f("amended_from", "Link", "Amended From", options="Pharmacy Dispense", read_only=1, no_copy=1, print_hide=1),
], autoname="format:DSP-.YYYY.-.#####", is_submittable=1, title_field="customer", icon="fa fa-plus-square",
	perms=perms((MGR, "full"), (PH, "full"), (ASST, "sub")))

# ------------------------------------------------------------------ transfers
doctype("Transfer Item", [
	f("item_code", "Link", "Item", options="Item", reqd=1, in_list_view=1),
	f("item_name", "Data", "Item Name", read_only=1, in_list_view=1),
	f("uom", "Link", "Unit", options="UOM", in_list_view=1),
	f("conversion_factor", "Float", "Units in Stock Unit", default=1, read_only=1),
	f("qty", "Float", "Quantity", reqd=1, default=1, in_list_view=1),
	f("batch_no", "Link", "Batch", options="Batch", description="Leave empty to take the batch that expires first."),
	f("expiry_date", "Date", "Expiry", read_only=1, in_list_view=1),
	f("batches", "Small Text", "Batches Used", read_only=1),
], istable=1)

doctype("Pharmacy Transfer", [
	f("transfer_type", "Select", "Type", options="Branch Transfer\nMove to Expired Stock\nWrite Off", default="Branch Transfer", reqd=1, in_list_view=1, in_standard_filter=1),
	f("posting_date", "Date", "Date", reqd=1, default="Today", in_list_view=1),
	col("cb1"),
	f("from_branch", "Link", "From Branch", options="Pharmacy Branch", reqd=1, in_list_view=1),
	f("to_branch", "Link", "To Branch", options="Pharmacy Branch", depends_on="eval:doc.transfer_type=='Branch Transfer'", mandatory_depends_on="eval:doc.transfer_type=='Branch Transfer'"),
	sec("sb_items", "Items"),
	f("items", "Table", "Items", options="Transfer Item", reqd=1),
	sec("sb_more", "Details"),
	f("reason", "Small Text", "Reason"),
	f("stock_entry", "Link", "Stock Entry", options="Stock Entry", read_only=1),
	f("company", "Link", "Company", options="Company", read_only=1, fetch_from="from_branch.company"),
	f("amended_from", "Link", "Amended From", options="Pharmacy Transfer", read_only=1, no_copy=1, print_hide=1),
], autoname="format:PTR-.YYYY.-.#####", is_submittable=1, icon="fa fa-exchange",
	perms=perms((MGR, "full"), (PH, "full"), (ASST, "sub"), (BUY, "r")))

# ------------------------------------------------------------------ purchasing
doctype("Supplier Offer", [
	f("supplier", "Link", "Supplier / Company", options="Supplier", reqd=1, in_list_view=1, in_standard_filter=1),
	f("item_code", "Link", "Item", options="Item", reqd=1, in_list_view=1, in_standard_filter=1),
	f("item_name", "Data", "Item Name", read_only=1, fetch_from="item_code.item_name"),
	f("price", "Currency", "Price per Unit", in_list_view=1, description="0 = the item's last purchase price."),
	f("discount_pct", "Percent", "Discount %", in_list_view=1),
	col("cb1"),
	f("min_qty", "Float", "Minimum Quantity"),
	f("bonus_per", "Float", "For Every (units bought)", description="Example: buy 10 ..."),
	f("bonus_qty", "Float", "Get Free (units)", description="... get 1 free."),
	sec("sb_v", "Validity"),
	f("valid_from", "Date", "Valid From"),
	f("valid_to", "Date", "Valid Until", in_list_view=1),
	f("payment_days", "Int", "Payment Days"),
	f("active", "Check", "Active", default=1),
], autoname="format:OFR-.#####", icon="fa fa-percent", perms=perms((MGR, "all"), (BUY, "all"), (PH, "r")))

doctype("Plan Branch", [f("branch", "Link", "Branch", options="Pharmacy Branch", reqd=1, in_list_view=1)], istable=1)

doctype("Purchase Plan Row", [
	f("include", "Check", "Order", default=1, in_list_view=1),
	f("item_code", "Link", "Item", options="Item", read_only=1, in_list_view=1),
	f("item_name", "Data", "Item Name", read_only=1),
	f("supplier", "Link", "Supplier", options="Supplier", in_list_view=1),
	f("stock", "Float", "Stock", read_only=1, in_list_view=1),
	f("on_order", "Float", "On Order", read_only=1),
	f("daily_sales", "Float", "Sold per Day", read_only=1, precision="3"),
	f("order_qty", "Float", "Order Quantity", in_list_view=1, description="Units received, free units included."),
	f("bonus_qty", "Float", "Free Units", read_only=1),
	f("unit_cost", "Currency", "Cost per Unit Received", in_list_view=1),
	f("amount", "Currency", "Amount", read_only=1),
	f("offer", "Link", "Offer Used", options="Supplier Offer", read_only=1),
	f("note", "Data", "Note", read_only=1),
], istable=1)

doctype("Pharmacy Purchase Plan", [
	f("company", "Link", "Company", options="Company", reqd=1),
	f("receiving_branch", "Link", "Deliver To", options="Pharmacy Branch", reqd=1, description="Usually the central store."),
	f("posting_date", "Date", "Date", reqd=1, default="Today"),
	col("cb1"),
	f("cover_days", "Int", "Days of Sales to Keep"),
	f("lookback_days", "Int", "Days of Sales History"),
	sec("sb_br", "Branches Counted"),
	f("branches", "Table", "Branches", options="Plan Branch", description="Stock and sales of these branches (and the receiving store) are counted together. Empty = every active branch."),
	sec("sb_rows", "Needs"),
	f("rows", "Table", "Needs", options="Purchase Plan Row"),
	sec("sb_res", "Result"),
	f("status", "Select", "Status", options="Draft\nLoaded\nOrdered", default="Draft", read_only=1, in_list_view=1, in_standard_filter=1),
	f("total_amount", "Currency", "Total", read_only=1, in_list_view=1),
	f("orders_made", "Small Text", "Purchase Orders Created", read_only=1),
	f("notes_html", "Text Editor", "Notes", read_only=1),
], autoname="format:PPP-.YYYY.-.#####", icon="fa fa-shopping-cart", perms=perms((MGR, "all"), (BUY, "all"), (PH, "r")))

# ------------------------------------------------------------------ patients
doctype("Refill Plan", [
	f("customer", "Link", "Patient", options="Customer", reqd=1, in_list_view=1, in_standard_filter=1),
	f("item_code", "Link", "Medicine", options="Item", reqd=1, in_list_view=1),
	f("item_name", "Data", "Item Name", read_only=1, fetch_from="item_code.item_name"),
	f("qty", "Float", "Quantity per Refill", default=1, reqd=1),
	f("every_days", "Int", "Every (days)", default=30, reqd=1, in_list_view=1),
	col("cb1"),
	f("branch", "Link", "Usual Branch", options="Pharmacy Branch"),
	f("start_date", "Date", "Start Date", default="Today"),
	f("last_dispensed", "Date", "Last Dispensed", read_only=1),
	f("next_due", "Date", "Next Refill Due", read_only=1, in_list_view=1),
	f("status", "Select", "Status", options="Not Started\nUpcoming\nDue Soon\nOverdue\nStopped", default="Not Started", read_only=1, in_list_view=1, in_standard_filter=1),
	f("stopped", "Check", "Stopped"),
	f("last_reminded", "Date", "Last Reminded", read_only=1),
	f("notes", "Small Text", "Notes"),
], autoname="format:RFL-.#####", title_field="customer", icon="fa fa-refresh", perms=perms((MGR, "all"), (PH, "all"), (ASST, "rwc")))

doctype("Controlled Drug Log", [
	f("posting_date", "Date", "Date", read_only=1, in_list_view=1),
	f("branch", "Link", "Branch", options="Pharmacy Branch", read_only=1, in_list_view=1, in_standard_filter=1),
	f("item_code", "Link", "Item", options="Item", read_only=1, in_list_view=1),
	f("item_name", "Data", "Item Name", read_only=1),
	f("batch_no", "Data", "Batch", read_only=1),
	f("qty", "Float", "Quantity", read_only=1, in_list_view=1),
	col("cb1"),
	f("customer", "Link", "Patient", options="Customer", read_only=1),
	f("patient_id", "Data", "Patient National ID", read_only=1),
	f("doctor", "Data", "Doctor", read_only=1),
	f("prescription_no", "Data", "Prescription No.", read_only=1, in_list_view=1),
	sec("sb2", "Source"),
	f("sales_invoice", "Link", "Sales Invoice", options="Sales Invoice", read_only=1),
	f("cancelled", "Check", "Cancelled", read_only=1, in_standard_filter=1),
	f("balance_after", "Float", "Branch Balance After", read_only=1),
], autoname="format:CDL-.YYYY.-.#####", icon="fa fa-lock", perms=perms((MGR, "r"), (PH, "r")))


def build():
	os.makedirs(ROOT, exist_ok=True)
	for name, d in DT.items():
		fields = d["fields"]
		order = [x["fieldname"] for x in fields]
		istable = d.get("istable", 0)
		out = {
			"actions": [], "creation": TS, "doctype": "DocType", "engine": "InnoDB", "field_order": order, "fields": fields,
			"links": [], "modified": TS, "modified_by": "Administrator", "module": MODULE, "name": name, "owner": "Administrator",
			"sort_field": "creation", "sort_order": "DESC", "states": [],
			"permissions": [] if istable else d.get("perms", []),
		}
		for k in ("autoname", "title_field", "icon", "track_changes", "issingle", "istable", "show_title_field_in_link", "search_fields", "is_submittable"):
			if k in d:
				out[k] = d[k]
		if name in ("Pharmacy Dispense", "Pharmacy Transfer", "Pharmacy Purchase Plan", "Refill Plan", "Insurance Plan", "Pharmacy Branch"):
			out["track_changes"] = 1
		if "autoname" not in d and not istable and not d.get("issingle"):
			out["autoname"] = "hash"
		out["allow_rename"] = 0
		slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
		folder = os.path.join(ROOT, slug)
		os.makedirs(folder, exist_ok=True)
		open(os.path.join(folder, "__init__.py"), "a").close()
		with open(os.path.join(folder, slug + ".json"), "w", encoding="utf-8") as fh:
			json.dump(out, fh, indent=1, ensure_ascii=False)
			fh.write("\n")
		py = os.path.join(folder, slug + ".py")
		if not os.path.exists(py):
			cls = "".join(w.capitalize() for w in re.split(r"[^A-Za-z0-9]+", name))
			with open(py, "w") as fh:
				fh.write(f"from frappe.model.document import Document\n\n\nclass {cls}(Document):\n\tpass\n")


if __name__ == "__main__":
	build()
	print(len(DT), "doctypes")
