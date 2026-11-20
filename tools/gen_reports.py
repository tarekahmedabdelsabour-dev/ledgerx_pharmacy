"""Writes the report JSON files. Run from the repo root. The .py/.js of each report are hand written and never overwritten."""
import json
import os

BASE = os.path.join(os.path.dirname(__file__), "..", "ledgerx_pharmacy", "pharmacy", "report")
TS = "2026-11-21 08:00:00.000000"
ROLES = ["Pharmacy Manager", "Pharmacist", "Pharmacy Buyer", "Stock Manager", "Accounts Manager"]
REPORTS = [
	("Expiry Report", "Pharmacy Branch"), ("Drug Alternatives", "Item"), ("Branch Performance", "Pharmacy Branch"),
	("Controlled Drug Register", "Controlled Drug Log"), ("Insurance Receivable", "Insurance Company"), ("Refills Due", "Refill Plan"),
]
for name, ref in REPORTS:
	slug = name.lower().replace(" ", "_")
	folder = os.path.join(BASE, slug)
	os.makedirs(folder, exist_ok=True)
	open(os.path.join(folder, "__init__.py"), "a").close()
	roles = ROLES + (["Auditor"] if name == "Controlled Drug Register" else [])
	if name == "Insurance Receivable":
		roles = ["Pharmacy Manager", "Accounts Manager", "Accounts User"]
	with open(os.path.join(folder, slug + ".json"), "w") as fh:
		json.dump({"add_total_row": 0, "columns": [], "creation": TS, "disabled": 0, "docstatus": 0, "doctype": "Report", "filters": [], "idx": 0, "is_standard": "Yes",
			"modified": TS, "modified_by": "Administrator", "module": "Pharmacy", "name": name, "owner": "Administrator", "prepared_report": 0, "ref_doctype": ref,
			"report_name": name, "report_type": "Script Report", "roles": [{"role": r} for r in roles]}, fh, indent=1)
		fh.write("\n")
print(len(REPORTS), "reports")
