frappe.query_reports["Controlled Drug Register"] = {
	filters: [
		{ fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Pharmacy Branch" },
		{ fieldname: "item_code", label: __("Item"), fieldtype: "Link", options: "Item", get_query: () => ({ filters: { ph_class: "Controlled" } }) },
		{ fieldname: "from_date", label: __("From"), fieldtype: "Date", default: frappe.datetime.month_start() },
		{ fieldname: "to_date", label: __("To"), fieldtype: "Date", default: frappe.datetime.get_today() },
		{ fieldname: "include_cancelled", label: __("Show Cancelled"), fieldtype: "Check" },
	],
};
