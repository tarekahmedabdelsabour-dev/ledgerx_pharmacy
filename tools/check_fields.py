"""Static check: every attribute a controller reads on a document or row exists as a field of some pharmacy DocType (or is a known Frappe attribute)."""
import glob
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..", "ledgerx_pharmacy")
fields = set()
for f in glob.glob(os.path.join(ROOT, "pharmacy", "doctype", "*", "*.json")):
	for x in json.load(open(f))["fields"]:
		fields.add(x["fieldname"])
KNOWN = set("""name doctype idx docstatus parent owner creation modified flags db_set check_permission append get items rows save insert submit cancel reload validate is_new
branches get_doc_before_save has_value_changed status company customer posting_date set grand_total outstanding_amount debit_to net_total taxes_and_charges set_taxes
stock_qty qty uom item_code warehouse batch_no amount rate stock_uom conversion_factor item_name price_list_rate discount_percentage cost_center set_warehouse
selling_price_list update_stock set_posting_time ignore_pricing_rule remarks supplier transaction_date schedule_date set_warehouse voucher_type user_remark accounts
payment_type party_type party paid_from paid_to paid_from_account_currency paid_to_account_currency paid_amount received_amount source_exchange_rate target_exchange_rate
reference_no reference_date mode_of_payment references stock_entry_type from_warehouse to_warehouse expense_account serial_and_batch_bundle is_return
default_receivable_account stock_adjustment_account manager_user expiry_date valuation_rate actual_qty ordered_qty end_of_life disabled is_stock_item has_batch_no purchase_uom
default_currency last_purchase_rate stock_uom expiry insurer customer_name territory customer_group customer_type _plan _branches refresh_status remarks""".split())
bad = {}
for f in glob.glob(os.path.join(ROOT, "pharmacy", "doctype", "*", "*.py")) + [os.path.join(ROOT, "items.py")]:
	src = open(f).read()
	for m in re.finditer(r"\b(?:self|doc|r|row|plan|p|si|pe|je|se|po|plan_doc|o|d|x|it|b|s|fb|tb|src|dst|recv|branch)\.([a-z_][a-z0-9_]*)\b(?!\()", src):
		n = m.group(1)
		if n not in fields and n not in KNOWN:
			bad.setdefault(os.path.basename(f), set()).add(n)
for k, v in bad.items():
	print(k, sorted(v))
print("unknown attributes:", sum(len(v) for v in bad.values()))
