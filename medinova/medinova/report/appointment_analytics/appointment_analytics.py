# Copyright (c) 2025, chai and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def execute(filters=None):
    columns = [
        {
            "label": _("Appointment ID"),
            "fieldname": "appointment_id",
            "fieldtype": "Data",
            "width": 160
        },
        {
            "label": _("Appointment Date"),
            "fieldname": "appointment_date",
            "fieldtype": "Date",
            "width": 120
        },
        {
            "label": _("Patient"),
            "fieldname": "patient",
            "fieldtype": "Link",
            "options": "Patient",
            "width": 200
        },
        {
            "label": _("Practitioner"),
            "fieldname": "practitioner",
            "fieldtype": "Link",
            "options": "Practitioner",
            "width": 200
        },
        {
            "label": _("Appointment Type"),
            "fieldname": "appointment_type",
            "fieldtype": "Link",
            "options": "Appointment Type",
            "width": 150
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": _("Consultation Fee"),
            "fieldname": "consultation_fee",
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "label": _("Payment Status"),
            "fieldname": "payment_status",
            "fieldtype": "Data",
            "width": 120
        },
    ]

    conditions = ""
    if filters.get("practitioner"):
        conditions += f" AND app.practitioner = {frappe.db.escape(filters.get('practitioner'))}"
    if filters.get("appointment_type"):
        conditions += f" AND app.appointment_type = {frappe.db.escape(filters.get('appointment_type'))}"
    if filters.get("status"):
        conditions += f" AND app.status = {frappe.db.escape(filters.get('status'))}"
    if filters.get("from_date") and filters.get("to_date"):
        conditions += f" AND app.appointment_date BETWEEN {frappe.db.escape(filters.get('from_date'))} AND {frappe.db.escape(filters.get('to_date'))}"

    sql_query = f"""
        SELECT
            -- FIX 2: Select 'app.appointment_id' to match the fieldname defined in the columns list.
            app.appointment_id, 
            app.appointment_date, 
            app.patient, 
            app.practitioner,
            app.appointment_type, 
            app.status, 
            prac.consultation_fee, 
            app.payment_status
        FROM `tabMake Appointment` as app
        LEFT JOIN `tabPractitioner` as prac ON app.practitioner = prac.name
        WHERE 1=1 {conditions}
        ORDER BY app.appointment_date DESC, app.start_time DESC
    """

    print("--- APPOINTMENT ANALYTICS REPORT DEBUG ---")
    print("Filters received:", filters)
    print("Generated SQL Query:", sql_query)

    data = frappe.db.sql(sql_query, as_dict=True)

    message = ""
    if not data:
        message = "No appointments found for the selected filters. Please check your bench console for the exact SQL query that was run."

    return columns, data, message