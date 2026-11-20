frappe.query_reports["Insurance Receivable"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company") },
		{ fieldname: "insurance_company", label: __("Insurance Company"), fieldtype: "Link", options: "Insurance Company" },
		{ fieldname: "as_of", label: __("As of"), fieldtype: "Date", default: frappe.datetime.get_today() },
	],
};
