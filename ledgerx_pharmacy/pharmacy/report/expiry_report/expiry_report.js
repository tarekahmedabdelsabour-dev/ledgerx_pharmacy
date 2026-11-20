frappe.query_reports["Expiry Report"] = {
	filters: [
		{ fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Pharmacy Branch" },
		{ fieldname: "status", label: __("Status"), fieldtype: "Select", options: ["", "Needs Action", "Expired", "Critical", "Near Expiry", "All"], default: "Needs Action" },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "status" && data) {
			const c = { Expired: "red", Critical: "orange", "Near Expiry": "yellow" }[data.status];
			if (c) value = `<span class="indicator-pill ${c}">${data.status}</span>`;
		}
		return value;
	},
};
