// Copyright (c) 2025, chai and contributors
// For license information, please see license.txt

frappe.query_reports["Appointment Analytics"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1), 
            "reqd": 1 
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1 
        },
        {
            "fieldname": "practitioner",
            "label": __("Practitioner"),
            "fieldtype": "Link",
            "options": "Practitioner" 
        },
        {
            "fieldname": "appointment_type",
            "label": __("Appointment Type"),
            "fieldtype": "Link",
            "options": "Appointment Type" 
        },
        {
            "fieldname": "status",
            "label": __("Status"),
            "fieldtype": "Select",
            "options": "\nBooked\nConfirmed\nChecked-in\nCompleted\nCancelled\nNo-show"
        }
    ]
};