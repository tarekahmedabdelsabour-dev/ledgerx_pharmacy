"""Demo data for the Pharmacy app: branches for the Egypt and Saudi companies, drugs with batches and expiry, opening stock,
insurers and plans, patients, dispenses (cash, insured, controlled with prescription), branch transfers, refill plans and supplier offers.

    bench --site mysite.localhost execute ledgerx_pharmacy.demo.run

Run ledgerx.demo.foundation first (companies, cost centers, warehouses). Take a backup first.
Idempotent: every record is looked up by its natural key before it is created. Every step commits on its own and reports its result;
failures are logged in Error Log under titles starting 'Demo pharmacy'. Run as Administrator (bench execute does).
Stock is received 45 days back so the dispenses can be dated in the past (charts and refill statuses then have history).
"""
import frappe
from frappe.utils import add_days, flt, nowdate

from ledgerx.shared import run_each

EGYPT, SAUDI = "LedgerX Egypt", "LedgerX Saudi"
PL = {EGYPT: "Pharmacy Public EGP", SAUDI: "Pharmacy Public SAR"}
PL_CCY = {"Pharmacy Public EGP": "EGP", "Pharmacy Public SAR": "SAR"}
GROUP = "Pharmacy Products"
STOCK_DAYS_BACK = 45

# branch, company, central, cost center, warehouse, license, phone, address
BRANCHES = [
	("Cairo Central Pharmacy", EGYPT, 1, "Cairo - LXE", "Cairo Store - LXE", "EG-PH-10458", "+20 2 2795 5100", "12 Road 9, Maadi, Cairo"),
	("Alexandria Pharmacy", EGYPT, 0, "Alexandria - LXE", "Alexandria Store - LXE", "EG-PH-20871", "+20 3 545 3300", "45 Fouad Street, Alexandria"),
	("Giza Pharmacy", EGYPT, 0, "Giza - LXE", "Giza Store - LXE", "EG-PH-30192", "+20 2 3337 6600", "8 Mossadak Street, Dokki, Giza"),
	("Riyadh Pharmacy", SAUDI, 1, "Riyadh - LXS", "Riyadh Store - LXS", "SA-MOH-RY-5521", "+966 11 462 8000", "Olaya Street, Riyadh"),
	("Jeddah Pharmacy", SAUDI, 0, "Jeddah - LXS", "Jeddah Store - LXS", "SA-MOH-JD-7743", "+966 12 667 4000", "Tahlia Street, Jeddah"),
]
STOCK_FACTOR = {"Cairo Central Pharmacy": 1.0, "Alexandria Pharmacy": 0.5, "Giza Pharmacy": 0.4, "Riyadh Pharmacy": 1.0, "Jeddah Pharmacy": 0.5}
INGREDIENTS = ["Amoxicillin", "Amoxicillin/Clavulanate", "Atorvastatin", "Omeprazole", "Metformin", "Insulin Glargine", "Paracetamol", "Ibuprofen", "Loratadine",
	"Oral Rehydration Salts", "Ascorbic Acid", "Cholecalciferol", "Zinc Oxide", "Tramadol", "Diazepam"]

# code, name, class, ingredient, strength, form, EGP price, SAR price, EGP cost, SAR cost, extra batches [(tag, days to expiry)], cold chain
ITEMS = [
	("LXP-AMOX500", "Amoxicillin 500 mg Capsules", "Prescription", "Amoxicillin", "500 mg", "Capsule", 85, 16, 55, 10, [("C", 21)], 0),
	("LXP-AMOX500B", "Amoxicillin 500 mg Capsules (Brand B)", "Prescription", "Amoxicillin", "500 mg", "Capsule", 78, 15, 50, 9, [], 0),
	("LXP-AUG1G", "Amoxicillin/Clavulanate 1 g Tablets", "Prescription", "Amoxicillin/Clavulanate", "1 g", "Tablet", 210, 38, 140, 25, [], 0),
	("LXP-ATOR20", "Atorvastatin 20 mg Tablets", "Prescription", "Atorvastatin", "20 mg", "Tablet", 140, 24, 90, 15, [("N", 75)], 0),
	("LXP-ATOR20B", "Atorvastatin 20 mg Tablets (Brand B)", "Prescription", "Atorvastatin", "20 mg", "Tablet", 125, 22, 80, 13, [], 0),
	("LXP-OMEP20", "Omeprazole 20 mg Capsules", "Prescription", "Omeprazole", "20 mg", "Capsule", 95, 16, 60, 10, [], 0),
	("LXP-MET500", "Metformin 500 mg Tablets", "Prescription", "Metformin", "500 mg", "Tablet", 50, 9, 30, 5, [], 0),
	("LXP-GLARG", "Insulin Glargine 100 IU/ml Pen", "Prescription", "Insulin Glargine", "100 IU/ml", "Injection", 480, 85, 320, 56, [("C", 25)], 1),
	("LXP-PARA500", "Paracetamol 500 mg Tablets", "OTC", "Paracetamol", "500 mg", "Tablet", 30, 5, 18, 3, [("N", 70)], 0),
	("LXP-PARA500B", "Paracetamol 500 mg Film-Coated Tablets (Brand B)", "OTC", "Paracetamol", "500 mg", "Tablet", 28, 5, 17, 3, [], 0),
	("LXP-IBU400", "Ibuprofen 400 mg Tablets", "OTC", "Ibuprofen", "400 mg", "Tablet", 45, 8, 28, 5, [("C", 18)], 0),
	("LXP-LORA10", "Loratadine 10 mg Tablets", "OTC", "Loratadine", "10 mg", "Tablet", 35, 6, 21, 4, [("N", 60)], 0),
	("LXP-ORS", "Oral Rehydration Salts Sachets", "OTC", "Oral Rehydration Salts", "", "Sachet", 12, 3, 7, 2, [], 0),
	("LXP-VITC", "Vitamin C 1000 mg Effervescent Tablets", "Supplement", "Ascorbic Acid", "1000 mg", "Tablet", 90, 18, 55, 11, [("N", 80)], 0),
	("LXP-D3", "Vitamin D3 50,000 IU Capsules", "Supplement", "Cholecalciferol", "50000 IU", "Capsule", 120, 22, 75, 14, [], 0),
	("LXP-SUN50", "Sunscreen SPF 50 Cream", "Cosmetic", "Zinc Oxide", "", "Cream", 260, 55, 160, 34, [("C", 28)], 0),
	("LXP-TRAM50", "Tramadol 50 mg Capsules", "Controlled", "Tramadol", "50 mg", "Capsule", 95, 20, 60, 13, [], 0),
	("LXP-DIAZ5", "Diazepam 5 mg Tablets", "Controlled", "Diazepam", "5 mg", "Tablet", 60, 12, 38, 8, [], 0),
]
BASE_QTY = {"Prescription": 120, "OTC": 240, "Controlled": 60, "Supplement": 100, "Cosmetic": 60}
EXTRA_QTY = {"C": 30, "N": 40}

# insurer, payment days
INSURERS = [("Pyramid Health Insurance", 45), ("Hijaz Medical Insurance", 30)]
# insurer, plan, cover %, patient cap, min copay
PLANS = [
	("Pyramid Health Insurance", "Gold", 80, 0, 0), ("Pyramid Health Insurance", "Standard", 70, 500, 10),
	("Hijaz Medical Insurance", "Premium", 90, 0, 0), ("Hijaz Medical Insurance", "Basic", 70, 300, 5),
]
SUPPLIERS = [("Mena Pharma Distribution", EGYPT), ("Gulf Medical Wholesale", SAUDI)]
# supplier, item, price (cost), discount %, min qty, bonus per, bonus qty, payment days
OFFERS = [
	("Mena Pharma Distribution", "LXP-AMOX500", 52, 5, 100, 10, 1, 60), ("Mena Pharma Distribution", "LXP-PARA500", 17, 8, 200, 20, 2, 45),
	("Mena Pharma Distribution", "LXP-ATOR20", 86, 4, 50, 0, 0, 60), ("Gulf Medical Wholesale", "LXP-OMEP20", 9.5, 6, 100, 25, 2, 45),
	("Gulf Medical Wholesale", "LXP-MET500", 4.8, 5, 200, 0, 0, 60),
]

# key -> customer. plan = (insurer, plan name)
PATIENTS = {
	"hanan": dict(name="Hanan Mahmoud Ali", nid="27505220112364", plan=("Pyramid Health Insurance", "Gold"), member="PHI-G-310045", notes="Hypertension, high cholesterol", territory="Egypt"),
	"tamer": dict(name="Tamer Sobhy Nasr", nid="26812032107152", plan=("Pyramid Health Insurance", "Standard"), member="PHI-S-220918", notes="Type 2 diabetes, on insulin", territory="Egypt"),
	"dina": dict(name="Dina Ashraf Kamel", nid="29502140203380", plan=None, member=None, notes="", territory="Egypt"),
	"ibrahim": dict(name="Ibrahim Hosny Fouad", nid="25909090104536", plan=None, member=None, notes="Chronic back pain", territory="Egypt"),
	"sultan": dict(name="Sultan Mohammed Al-Dosari", nid="1054321876", plan=("Hijaz Medical Insurance", "Premium"), member="HMI-884201", notes="Reflux, high cholesterol", territory="Saudi Arabia"),
	"maha": dict(name="Maha Abdullah Al-Zahrani", nid="1098765432", plan=None, member=None, notes="Vitamin D deficiency", territory="Saudi Arabia"),
	"turki": dict(name="Turki Nasser Al-Shehri", nid="1076543219", plan=("Hijaz Medical Insurance", "Basic"), member="HMI-551930", notes="Anxiety disorder", territory="Saudi Arabia"),
}
# chronic patients: key, item, qty, every days, branch, start offset (days ago)
REFILLS = [
	("hanan", "LXP-ATOR20", 2, 30, "Cairo Central Pharmacy", 40),
	("tamer", "LXP-MET500", 3, 30, "Giza Pharmacy", 20),
	("tamer", "LXP-GLARG", 2, 28, "Giza Pharmacy", 26),
	("sultan", "LXP-OMEP20", 2, 30, "Riyadh Pharmacy", 4),
]
# branch, days ago, patient (None = walk-in), doctor, prescription no, [(item, qty, discount %)]
DISPENSES = [
	("Cairo Central Pharmacy", 40, "hanan", "Dr. Samir Fawzy", "RX-EG-2611-0417", [("LXP-ATOR20", 2, 0)]),
	("Cairo Central Pharmacy", 9, None, None, None, [("LXP-PARA500", 2, 0), ("LXP-ORS", 3, 0)]),
	("Giza Pharmacy", 26, "tamer", "Dr. Ayman Reda", "RX-EG-2611-0533", [("LXP-GLARG", 2, 0)]),
	("Giza Pharmacy", 20, "tamer", "Dr. Ayman Reda", "RX-EG-2611-0612", [("LXP-MET500", 3, 0), ("LXP-OMEP20", 1, 0)]),
	("Cairo Central Pharmacy", 8, "hanan", "Dr. Samir Fawzy", "RX-EG-2611-0701", [("LXP-OMEP20", 1, 0), ("LXP-SUN50", 1, 0)]),
	("Cairo Central Pharmacy", 5, None, None, None, [("LXP-IBU400", 1, 0), ("LXP-LORA10", 1, 0), ("LXP-VITC", 2, 5)]),
	("Cairo Central Pharmacy", 3, "ibrahim", "Dr. Wael Barakat", "RX-EG-2611-0788", [("LXP-TRAM50", 1, 0)]),
	("Alexandria Pharmacy", 7, "dina", "Dr. Omar Ibrahim", "RX-EG-2611-0655", [("LXP-AMOX500", 2, 0), ("LXP-PARA500", 1, 0)]),
	("Alexandria Pharmacy", 2, None, None, None, [("LXP-ORS", 4, 0), ("LXP-IBU400", 1, 0)]),
	("Riyadh Pharmacy", 4, "sultan", "Dr. Khalid Al-Mutairi", "RX-SA-2611-3120", [("LXP-OMEP20", 2, 0), ("LXP-ATOR20", 1, 0)]),
	("Riyadh Pharmacy", 2, "turki", "Dr. Khalid Al-Mutairi", "RX-SA-2611-3187", [("LXP-DIAZ5", 1, 0)]),
	("Riyadh Pharmacy", 0, None, None, None, [("LXP-PARA500", 2, 0), ("LXP-VITC", 1, 0)]),
	("Jeddah Pharmacy", 3, "maha", None, None, [("LXP-D3", 1, 0), ("LXP-VITC", 1, 0), ("LXP-PARA500", 1, 0)]),
]
# from, to, days ago, reason, [(item, qty)]
TRANSFERS = [
	("Cairo Central Pharmacy", "Giza Pharmacy", 3, "Demo: weekly replenishment of Giza", [("LXP-AMOX500", 20), ("LXP-PARA500", 40), ("LXP-IBU400", 30), ("LXP-ORS", 50)]),
	("Riyadh Pharmacy", "Jeddah Pharmacy", 1, "Demo: insulin and antibiotics for Jeddah", [("LXP-GLARG", 10), ("LXP-AUG1G", 20)]),
]


def _say(msg):
	print(msg)


def _insert(doc):
	return frappe.get_doc(doc).insert(ignore_permissions=True)


def _branch_row(name):
	return next(b for b in BRANCHES if b[0] == name)


def _mode(company):
	"""'Cash' when it has an account for the company, else a demo mode created with the company's default cash account."""
	if frappe.db.exists("Mode of Payment Account", {"parent": "Cash", "company": company}):
		return "Cash"
	acct = frappe.db.get_value("Company", company, "default_cash_account")
	if not acct:
		frappe.throw(f"Company {company} has no default cash account")
	if not frappe.db.exists("Mode of Payment", "Demo Cash"):
		_insert({"doctype": "Mode of Payment", "mode_of_payment": "Demo Cash", "type": "Cash", "enabled": 1})
	mode = frappe.get_doc("Mode of Payment", "Demo Cash")
	if not any(r.company == company for r in mode.accounts):
		mode.append("accounts", {"company": company, "default_account": acct})
		mode.save(ignore_permissions=True)
	return "Demo Cash"


def _price_list(name):
	if not frappe.db.exists("Price List", name):
		_insert({"doctype": "Price List", "price_list_name": name, "currency": PL_CCY[name], "selling": 1, "buying": 0, "enabled": 1})


def _item_price(code, pl, price):
	_price_list(pl)
	if not frappe.db.exists("Item Price", {"item_code": code, "price_list": pl, "selling": 1, "uom": "Nos"}):
		_insert({"doctype": "Item Price", "item_code": code, "price_list": pl, "selling": 1, "uom": "Nos", "price_list_rate": price, "currency": PL_CCY[pl]})


def _walk_in():
	return frappe.db.get_single_value("Pharmacy Settings", "walk_in_customer")


def _customer_group():
	return "Individual" if frappe.db.exists("Customer Group", "Individual") else frappe.db.get_value("Customer Group", {"is_group": 0}, "name")


# ------------------------------------------------------------------ masters
def _settings(_x):
	"""Fill Pharmacy Settings only where empty."""
	s = frappe.get_doc("Pharmacy Settings")
	if not s.company and frappe.db.exists("Company", EGYPT):
		frappe.db.set_single_value("Pharmacy Settings", "company", EGYPT)
	if not s.walk_in_customer:
		name = "Pharmacy Walk-in"
		if not frappe.db.exists("Customer", name):
			_insert({"doctype": "Customer", "customer_name": name, "customer_type": "Individual", "customer_group": _customer_group(),
				"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name")})
		frappe.db.set_single_value("Pharmacy Settings", "walk_in_customer", name)
	if not s.public_price_list:
		_price_list(PL[EGYPT])
		frappe.db.set_single_value("Pharmacy Settings", "public_price_list", PL[EGYPT])
	frappe.clear_document_cache("Pharmacy Settings", "Pharmacy Settings")


def _expired_warehouse(company):
	full = f"Pharmacy Expired Stock - {frappe.db.get_value('Company', company, 'abbr')}"
	if not frappe.db.exists("Warehouse", full):
		_insert({"doctype": "Warehouse", "warehouse_name": "Pharmacy Expired Stock", "company": company})
	return full


def _branch(name):
	_n, company, central, cc, wh, lic, phone, addr = _branch_row(name)
	if frappe.db.exists("Pharmacy Branch", name):
		return
	if not frappe.db.exists("Warehouse", wh):
		frappe.throw(f"Warehouse {wh} is missing. Run ledgerx.demo.foundation first.")
	_price_list(PL[company])
	_insert({"doctype": "Pharmacy Branch", "branch_name": name, "company": company, "is_central": central, "active": 1, "warehouse": wh,
		"expired_warehouse": _expired_warehouse(company), "cost_center": cc if frappe.db.exists("Cost Center", cc) else None, "price_list": PL[company],
		"license_no": lic, "license_expiry": add_days(nowdate(), 300), "phone": phone, "address": addr})


def _ingredient(name):
	if not frappe.db.exists("Active Ingredient", name):
		_insert({"doctype": "Active Ingredient", "ingredient_name": name})


def _group(_x):
	if not frappe.db.exists("Item Group", GROUP):
		_insert({"doctype": "Item Group", "item_group_name": GROUP, "parent_item_group": "All Item Groups", "is_group": 0})


def _item(code):
	_c, name, klass, ingr, strength, form, egp, sar, _ce, _cs, _extra, cold = next(i for i in ITEMS if i[0] == code)
	if not frappe.db.exists("Item", code):
		_insert({"doctype": "Item", "item_code": code, "item_name": name, "item_group": GROUP, "stock_uom": "Nos", "is_stock_item": 1, "description": name,
			"ph_is_drug": 1, "ph_class": klass, "ph_active_ingredient": ingr, "ph_strength": strength, "ph_form": form, "ph_public_price": egp, "ph_cold_chain": cold,
			"shelf_life_in_days": 730})
	_item_price(code, PL[EGYPT], egp)
	_item_price(code, PL[SAUDI], sar)


def _batches(code):
	item = next(i for i in ITEMS if i[0] == code)
	for tag, days in [("L", 540)] + item[10]:
		bid = f"{code}-{tag}"
		if not frappe.db.exists("Batch", bid):
			_insert({"doctype": "Batch", "batch_id": bid, "item": code, "manufacturing_date": add_days(nowdate(), days - 730), "expiry_date": add_days(nowdate(), days)})


def _stock(branch):
	"""Opening stock of every demo drug in the branch warehouse as one real Material Receipt, dated 45 days back."""
	_n, company, _c, cc, wh, *_r = _branch_row(branch)
	remark = f"Demo pharmacy opening stock - {wh}"
	if frappe.db.exists("Stock Entry", {"remarks": remark, "docstatus": 1}):
		return
	account = frappe.db.get_value("Company", company, "stock_adjustment_account")
	if not account:
		frappe.throw(f"Set the stock adjustment account on {company}")
	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Receipt"
	se.company = company
	se.posting_date = add_days(nowdate(), -STOCK_DAYS_BACK)
	se.set_posting_time = 1
	se.to_warehouse = wh
	se.remarks = remark
	f = STOCK_FACTOR[branch]
	for code, _nm, klass, _i, _s, _f, _pe, _ps, cost_e, cost_s, extra, cold in ITEMS:
		base = 40 if cold else BASE_QTY[klass]
		for tag, _d in [("L", 0)] + extra:
			qty = max(round((base if tag == "L" else EXTRA_QTY[tag]) * f), 5)
			row = {"item_code": code, "qty": qty, "uom": "Nos", "stock_uom": "Nos", "conversion_factor": 1, "t_warehouse": wh, "basic_rate": cost_e if company == EGYPT else cost_s,
				"batch_no": f"{code}-{tag}", "use_serial_batch_fields": 1, "expense_account": account}
			if frappe.db.exists("Cost Center", cc):
				row["cost_center"] = cc
			se.append("items", row)
	se.insert(ignore_permissions=True)
	se.submit()


def _insurer(name):
	if not frappe.db.exists("Insurance Company", name):
		_insert({"doctype": "Insurance Company", "company_name": name, "active": 1, "payment_days": dict(INSURERS)[name], "contact": "Claims desk"})


def _plan(i):
	insurer, plan, cover, cap, copay = PLANS[int(i)]
	if not frappe.db.exists("Insurance Plan", {"insurance_company": insurer, "plan_name": plan}):
		_insert({"doctype": "Insurance Plan", "insurance_company": insurer, "plan_name": plan, "cover_pct": cover, "patient_cap": cap, "min_copay": copay,
			"exclude_cosmetics": 1, "valid_to": add_days(nowdate(), 300), "active": 1})


def _plan_name(plan):
	return frappe.db.get_value("Insurance Plan", {"insurance_company": plan[0], "plan_name": plan[1]}, "name") if plan else None


def _customer(key):
	p = PATIENTS[key]
	if frappe.db.exists("Customer", p["name"]):
		return
	doc = {"doctype": "Customer", "customer_name": p["name"], "customer_type": "Individual", "customer_group": _customer_group(), "territory": p["territory"],
		"ph_national_id": p["nid"], "ph_chronic_notes": p["notes"]}
	if p["plan"]:
		doc.update({"ph_insurance_plan": _plan_name(p["plan"]), "ph_member_no": p["member"]})
	_insert(doc)


def _supplier(name):
	if not frappe.db.exists("Supplier", name):
		grp = "Distributor" if frappe.db.exists("Supplier Group", "Distributor") else frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
		_insert({"doctype": "Supplier", "supplier_name": name, "supplier_group": grp, "supplier_type": "Company"})


def _offer(i):
	sup, item, price, disc, minq, bper, bqty, days = OFFERS[int(i)]
	if frappe.db.exists("Supplier Offer", {"supplier": sup, "item_code": item}):
		return
	_insert({"doctype": "Supplier Offer", "supplier": sup, "item_code": item, "price": price, "discount_pct": disc, "min_qty": minq, "bonus_per": bper, "bonus_qty": bqty,
		"valid_from": nowdate(), "valid_to": add_days(nowdate(), 90), "payment_days": days, "active": 1})


def _refill(i):
	key, item, qty, every, branch, ago = REFILLS[int(i)]
	cust = PATIENTS[key]["name"]
	if frappe.db.exists("Refill Plan", {"customer": cust, "item_code": item}):
		return
	_insert({"doctype": "Refill Plan", "customer": cust, "item_code": item, "qty": qty, "every_days": every, "branch": branch, "start_date": add_days(nowdate(), -ago),
		"notes": "Chronic patient - monthly supply"})


# ------------------------------------------------------------------ transactions
def _dispense(i):
	"""A dispense from the branch warehouse. The pharmacy engine makes the sales invoice (stock out by batch), the insurer entry and the payment."""
	branch, ago, key, doctor, rx, lines = DISPENSES[int(i)]
	company = _branch_row(branch)[1]
	p = PATIENTS[key] if key else None
	customer = p["name"] if p else _walk_in()
	if not customer:
		frappe.throw("Set a walk-in customer in Pharmacy Settings")
	first_item, first_qty = lines[0][0], lines[0][1]
	if frappe.db.sql("""SELECT d.name FROM `tabPharmacy Dispense` d INNER JOIN `tabDispense Item` i ON i.parent = d.name
			WHERE d.docstatus = 1 AND d.branch = %s AND d.customer = %s AND i.item_code = %s AND i.qty = %s LIMIT 1""", (branch, customer, first_item, first_qty)):
		return
	doc = {"doctype": "Pharmacy Dispense", "branch": branch, "posting_date": add_days(nowdate(), -ago), "customer": customer, "doctor": doctor, "prescription_no": rx,
		"mode_of_payment": _mode(company), "items": [{"item_code": c, "qty": q, "discount_pct": d} for c, q, d in lines]}
	if p:
		doc["patient_id"] = p["nid"]
		if p["plan"]:
			doc.update({"insurance_plan": _plan_name(p["plan"]), "member_no": p["member"], "approval_no": f"APP-{p['member'][-4:]}-{ago:02d}"})
	_insert(doc).submit()


def _transfer(i):
	src, dst, ago, reason, lines = TRANSFERS[int(i)]
	if frappe.db.exists("Pharmacy Transfer", {"from_branch": src, "to_branch": dst, "reason": reason}):
		return
	_insert({"doctype": "Pharmacy Transfer", "transfer_type": "Branch Transfer", "posting_date": add_days(nowdate(), -ago), "from_branch": src, "to_branch": dst, "reason": reason,
		"items": [{"item_code": c, "qty": q} for c, q in lines]}).submit()


def _idx(seq):
	return [str(i) for i in range(len(seq))]


STEPS = [
	("Settings", _settings, [1]),
	("Branches", _branch, [b[0] for b in BRANCHES]),
	("Active ingredients", _ingredient, INGREDIENTS),
	("Item group", _group, [1]),
	("Drugs and prices", _item, [i[0] for i in ITEMS]),
	("Batches", _batches, [i[0] for i in ITEMS]),
	("Opening stock", _stock, [b[0] for b in BRANCHES]),
	("Insurers", _insurer, [i[0] for i in INSURERS]),
	("Insurance plans", _plan, _idx(PLANS)),
	("Patients", _customer, list(PATIENTS)),
	("Suppliers", _supplier, [s[0] for s in SUPPLIERS]),
	("Supplier offers", _offer, _idx(OFFERS)),
	("Refill plans", _refill, _idx(REFILLS)),
	("Dispenses", _dispense, _idx(DISPENSES)),
	("Branch transfers", _transfer, _idx(TRANSFERS)),
]


def run():
	_say("Pharmacy demo data")
	failed_any = False
	for label, fn, items in STEPS:
		done, failed = run_each(items, fn, f"Demo pharmacy: {label}")
		failed_any = failed_any or bool(failed)
		_say(f"  {label}: {len(done)} ok, {len(failed)} failed")
	if failed_any:
		_say("Some steps failed. Open Error Log (titles start with 'Demo pharmacy') and send me the errors.")
	else:
		_say("Done. Open the Pharmacy workspace: expiry report, controlled drug register, insurance receivable, refills due are filled.")
