import frappe
from datetime import datetime, timedelta
from frappe.utils import getdate, get_datetime, now_datetime

@frappe.whitelist()
def get_available_start_times(practitioner, appointment_date, appointment_type):
    """
    Finds available start times for a service with a variable duration by calculating
    the free "gaps" in a practitioner's schedule.
    """
    try:
        duration_mins = frappe.db.get_value("Appointment Type", appointment_type, "default_duration_mins")
        if not duration_mins:
            frappe.throw(f"Appointment Type '{appointment_type}' has no duration set.")
        required_duration = timedelta(minutes=duration_mins)
    except Exception:
        return {"available_slots": []} 

    date_obj = getdate(appointment_date)
    day_of_week = date_obj.strftime("%A")
    practitioner_doc = frappe.get_doc("Practitioner", practitioner)
    schedule = next((s for s in practitioner_doc.availability_schedule if s.day_of_week == day_of_week), None)
    if not schedule:
        return {"available_slots": []} 

    day_start = get_datetime(f"{appointment_date} {schedule.start_time}")
    day_end = get_datetime(f"{appointment_date} {schedule.end_time}")

    booked_appointments = frappe.get_all(
        "Make Appointment",
        filters={"practitioner": practitioner, "appointment_date": appointment_date, "status": ("!=", "Cancelled")},
        fields=["start_time", "end_time"],
        order_by="start_time"
    )

    available_start_times = []
    last_known_free_time = day_start

    for booking in booked_appointments:
        booking_start = get_datetime(f"{appointment_date} {booking.start_time}")
        booking_end = get_datetime(f"{appointment_date} {booking.end_time}")

        free_block_duration = booking_start - last_known_free_time
        if free_block_duration >= required_duration:
            potential_start = last_known_free_time
            while potential_start + required_duration <= booking_start:
                available_start_times.append(potential_start.strftime("%H:%M"))
                potential_start += timedelta(minutes=15)

        last_known_free_time = booking_end

    final_free_block_duration = day_end - last_known_free_time
    if final_free_block_duration >= required_duration:
        potential_start = last_known_free_time
        while potential_start + required_duration <= day_end:
            available_start_times.append(potential_start.strftime("%H:%M"))
            potential_start += timedelta(minutes=15)

    return {"available_slots": sorted(list(set(available_start_times)))}

@frappe.whitelist()
def update_past_appointment_statuses():
    now = now_datetime()
    
    past_appointments = frappe.get_all(
        "Make Appointment",
        filters=[
            ["status", "in", ("Booked", "Confirmed", "Checked-in")],
            ["CONCAT(`appointment_date`, ' ', `end_time`)", "<", now]
        ],
        pluck="name"
    )

    for appointment_name in past_appointments:
        try:
            doc = frappe.get_doc("Make Appointment", appointment_name)
            doc.status = "Completed"
            doc.save(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(message=str(e), title=f"Failed to update Appointment {appointment_name}")
    frappe.db.commit()
    
@frappe.whitelist()
def process_mock_payment(encounter_name):
    """
    Creates and submits a new 'Encounter Payment' document and links it back
    to the Patient Encounter.
    """
    encounter = frappe.get_doc("Patient Encounter", encounter_name)

    if encounter.payment_status == 'Paid':
        frappe.throw("This encounter has already been paid.")
        return

    payment = frappe.get_doc({
        "doctype": "Encounter Payment",
        "patient_encounter": encounter.name,
        "patient": encounter.patient,
        "payment_date": frappe.utils.today(),
        "amount_paid": encounter.grand_total,
        "mode_of_payment": "Cash" 
    })

    payment.insert(ignore_permissions=True)
    payment.submit()

    encounter.db_set('payment_status', 'Paid')
    encounter.db_set('payment_record', payment.name) 

    frappe.msgprint(f"Payment {payment.name} recorded successfully.")
    return {
        "payment_name": payment.name
    }
    
import frappe

@frappe.whitelist()
def calculate_encounter_bill(encounter_name):
    """
    Calculates the total bill for a Patient Encounter based on consultation,
    medicines, and other services, using valuation_rate for item costs.
    """
    encounter = frappe.get_doc("Patient Encounter", encounter_name)

    consultation_fee = frappe.db.get_value("Practitioner", encounter.practitioner, "consultation_fee") or 0

    medicine_cost = 0
    for prescription in encounter.prescriptions:
        item_price = frappe.db.get_value("Item", prescription.medicine, "valuation_rate") or 0
        medicine_cost += item_price

    service_cost = 0
    if hasattr(encounter, 'services_performed'):
        for service in encounter.services_performed:
            item_price = frappe.db.get_value("Item", service.service_item, "valuation_rate") or 0
            frappe.db.set_value("Performed Service", service.name, "cost", item_price, update_modified=False)
            service_cost += item_price

    grand_total = consultation_fee + medicine_cost + service_cost

    encounter.db_set('total_consultation_fee', consultation_fee)
    encounter.db_set('total_medicine_cost', medicine_cost)
    encounter.db_set('total_service_cost', service_cost)
    encounter.db_set('grand_total', grand_total)
    
    return {
        "grand_total": grand_total
    }
