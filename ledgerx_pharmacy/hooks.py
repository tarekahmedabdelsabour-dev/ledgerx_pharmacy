app_name = "ledgerx_pharmacy"
app_title = "Pharmacy"
app_publisher = "LedgerX"
app_description = "Pharmacy chains: batches and expiry, many branches with a central store, insurance and chronic patients, controlled drugs, smart purchasing"
app_email = "hello@ledgerx.local"
app_license = "mit"

required_apps = ["erpnext"]

add_to_apps_screen = [
	{
		"name": "ledgerx_pharmacy",
		"logo": "/assets/ledgerx_pharmacy/images/pharmacy.svg",
		"title": "Pharmacy",
		"route": "/desk/pharmacy",
		"has_permission": "ledgerx_pharmacy.install.check_app_permission",
	}
]

doc_events = {
	"Item": {"validate": "ledgerx_pharmacy.items.item_validate", "on_update": "ledgerx_pharmacy.items.item_on_update"},
	"Sales Invoice": {
		"validate": "ledgerx_pharmacy.items.invoice_validate",
		"on_submit": "ledgerx_pharmacy.items.invoice_on_submit",
		"on_cancel": "ledgerx_pharmacy.items.invoice_on_cancel",
	},
}

override_doctype_dashboards = {
	"Customer": "ledgerx_pharmacy.overrides.customer",
	"Item": "ledgerx_pharmacy.overrides.item",
	"Supplier": "ledgerx_pharmacy.overrides.supplier",
	"Sales Invoice": "ledgerx_pharmacy.overrides.sales_invoice",
	"Warehouse": "ledgerx_pharmacy.overrides.warehouse",
	"Employee": "ledgerx_pharmacy.overrides.employee",
}

scheduler_events = {
	"cron": {
		"30 5 * * *": ["ledgerx_pharmacy.tasks.refresh_refills", "ledgerx_pharmacy.tasks.refill_reminders"],
		"0 6 * * *": ["ledgerx_pharmacy.tasks.expiry_alerts"],
	},
}

from ledgerx_pharmacy import __version__ as _v  # noqa: E402

app_include_js = [f"/assets/ledgerx_pharmacy/js/pharmacy_forms.js?v={_v}"]

after_install = "ledgerx_pharmacy.install.after_install"
after_migrate = "ledgerx_pharmacy.install.after_migrate"
