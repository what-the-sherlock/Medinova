# Copyright (c) 2025, chai and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def get_context(context):
    """Context for web form."""
    context.show_sidebar = False
    context.no_cache = True
    context.page_title = _("New Appointment")
    return context


@frappe.whitelist(allow_guest=False)
def get_patient_details(patient):
    """Fetch patient contact and email based on selected patient."""
    if not patient:
        return {}

    data = frappe.db.get_value("Patient", patient, ["contact_number", "email"], as_dict=True)
    if not data:
        return {}

    return {
        "patient_contact": data.contact_number or "",
        "email": data.email or ""
    }


@frappe.whitelist(allow_guest=False)
def get_available_slots(practitioner, appointment_date, appointment_type):
    """Fetch available time slots from backend API."""
    if not (practitioner and appointment_date and appointment_type):
        frappe.log_error("❌ Missing required parameters for get_available_slots", "New Appointment")
        return []

    try:
        method = frappe.get_attr("medinova.api.get_available_start_times")
        response = method(
            practitioner=practitioner,
            appointment_date=appointment_date,
            appointment_type=appointment_type
        )
        frappe.log_error(
            message=f"✅ API Response: {frappe.as_json(response)}",
            title="get_available_slots"
        )
        return response.get("available_slots", []) if response else []

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Error fetching available slots (New Appointment)")
        return []


@frappe.whitelist(allow_guest=False)
def calculate_end_time(start_time, appointment_type):
    """Return calculated end time from start_time + default duration."""
    if not (start_time and appointment_type):
        return ""

    duration = frappe.db.get_value("Appointment Type", appointment_type, "default_duration_mins") or 30
    from datetime import datetime, timedelta
    try:
        start_dt = datetime.strptime(start_time, "%H:%M:%S")
    except ValueError:
        start_dt = datetime.strptime(start_time, "%H:%M")
    end_dt = start_dt + timedelta(minutes=int(duration))
    return end_dt.strftime("%H:%M:%S")
