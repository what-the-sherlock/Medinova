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
    
    
    
# ------------------------------------------------

from frappe.model.document import Document
import frappe
import google.generativeai as genai

@frappe.whitelist()
def summarize_clinical_notes(encounter_name):
    doc = frappe.get_doc("Patient Encounter", encounter_name)

    if not doc.clinical_notes:
        msg = "No clinical notes to summarize."
        doc.db_set('ai_summary', msg)
        return msg

    api_key = frappe.conf.get("gemini_api_key")
    if not api_key:
        msg = "Error: Gemini API key not set in site_config.json."
        frappe.log_error(msg, "AI Agent Error")
        doc.db_set('ai_summary', msg)
        return msg

    try:
        
        genai.configure(api_key=api_key)

        model = genai.GenerativeModel("models/gemini-2.5-pro")

        # 🧠 Enhanced instruction prompt
        prompt = f"""
        You are an expert medical language model assisting doctors.
        The following are rough, shorthand, or incomplete clinical notes written in a hurry.

        Your task:
        1. Interpret unclear medical shorthand or abbreviations.
        2. Expand them into clear, full sentences using accurate clinical language.
        3. Maintain the original meaning.
        4. Then summarize the key findings in 3–4 concise bullet points.

        Example Input:
        "pt c/o chest pain since morn. bp high. r/o cardiac."
        Example Output:
        "The patient complained of chest pain since the morning and had elevated blood pressure. Cardiac causes are to be ruled out."
        Summary:
        - Presented with chest pain and high BP
        - Possible cardiac cause under evaluation

        Clinical Notes:
        {doc.clinical_notes}

        Output:
        """

        response = model.generate_content(prompt)
        summary = response.text.strip()


        summary = summary[:1400]

        doc.db_set('ai_summary', summary)
        return summary

    except Exception as e:
        error_msg = f"Error: Gemini summarization failed. {str(e)}"
        frappe.log_error(error_msg, "AI Agent Error")
        doc.db_set('ai_summary', error_msg)
        return error_msg

#-------------------------------------------------------------------------

import frappe
import google.generativeai as genai
from frappe.utils import nowdate
import re, json

@frappe.whitelist()
def get_slots_from_natural_language(message, conversation_history):
    """
    Uses Gemini to interpret the user's message, extract entities, and return available slots.
    Also supports recognizing requests like "Show my last appointment".
    """
    api_key = frappe.conf.get("gemini_api_key")
    if not api_key:
        frappe.throw("Gemini API key is not set in site_config.json.")

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("models/gemini-2.5-flash")

        practitioners = frappe.get_all("Practitioner", fields=["name", "specialization"])
        appointment_types = frappe.get_all("Appointment Type", fields=["type_name"])

        prompt = f"""
        You are a medical appointment scheduling assistant.
        Today's date is {nowdate()}.

        Recognize what the user wants:
        - If they want to book an appointment, extract:
          1️⃣ practitioner — by name or specialization
          2️⃣ appointment_type
          3️⃣ appointment_date (convert words like 'tomorrow' to YYYY-MM-DD)
        - If the user asks for their "last appointment" or "my recent booking",
          just reply with the keyword: LAST_APPOINTMENT
        - If the user asks for "appointments this week" or "upcoming appointments",
          reply with the keyword: UPCOMING_APPOINTMENTS

        Available practitioners: {practitioners}
        Appointment types: {appointment_types}
        Conversation so far: {conversation_history}
        Latest user message: "{message}"

        Respond ONLY in one of these formats:
        - If booking intent detected and all info found:
          {{ "practitioner": "PR001", "appointment_type": "Dental Cleanup", "appointment_date": "2025-11-17" }}
        - If info missing: ask ONE follow-up question.
        - If they want last appointment: output ONLY LAST_APPOINTMENT
        - If they want upcoming appointments: output ONLY UPCOMING_APPOINTMENTS
        """

        response = model.generate_content(prompt)
        ai_response = response.text.strip()

    except Exception as e:
        frappe.log_error(f"Gemini NLU Error: {e}", "AI Chatbot Error")
        return {"message": f"AI understanding failed: {str(e)}"}


    try:
        # Handle special keywords first
        if ai_response == "LAST_APPOINTMENT":
            return get_last_appointment()
        elif ai_response == "UPCOMING_APPOINTMENTS":
            return get_upcoming_appointments()

        # Try to extract JSON even if wrapped in text
        match = re.search(r"\{.*\}", ai_response, re.DOTALL)
        if match:
            entities = frappe.parse_json(match.group(0))
        else:
            entities = None

        if not entities:
            return {"message": ai_response}

        # Ensure all fields exist
        required = ["practitioner", "appointment_type", "appointment_date"]
        if not all(k in entities for k in required):
            return {"message": "I need a bit more info — please specify the doctor or date."}

        # ✅ Get available slots from your custom API
        slots = frappe.call("medinova.api.get_available_start_times", **entities)
        if not slots.get("available_slots"):
            return {"message": f"Sorry, no slots available for {entities['practitioner']} on {entities['appointment_date']}."}

        return {"slots": slots.get("available_slots"), "entities": entities}

    except Exception as e:
        frappe.log_error(f"AI Parse Error: {e}\nResponse: {ai_response}", "AI Chatbot Error")
        return {"message": "I had trouble interpreting that — please rephrase your request."}


@frappe.whitelist()
def create_appointment_from_chat(patient_name, practitioner, appointment_date, start_time, appointment_type):
    """Creates appointment safely and logs errors."""
    try:
        patient_id = (
            frappe.db.get_value("Patient", {"full_name": patient_name})
            or frappe.db.get_value("Patient", {"email": frappe.session.user})
            or frappe.db.get_value("Patient", {"owner": frappe.session.user})
        )
        if not patient_id:
            frappe.throw(f"No patient found for {patient_name} or {frappe.session.user}")

        data = {
            "doctype": "Make Appointment",
            "patient": patient_id,
            "practitioner": practitioner,
            "appointment_date": appointment_date,
            "start_time": start_time,
            "appointment_type": appointment_type,
            "booking_channel": "Patient Portal",
            "status": "Booked"
        }

        appt = frappe.get_doc(data)
        appt.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "success": True,
            "appointment_name": appt.name,
            "message": f"✅ You’re all booked! Your appointment ID is <b>{appt.name}</b>."
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Chatbot Booking Failed (Debug)")
        return {"error": f"Sorry, I couldn’t finalize the booking. Error: {str(e)}"}


def get_last_appointment():
    """Fetches the most recent appointment for the logged-in user."""
    email = frappe.session.user
    patient_id = frappe.db.get_value("Patient", {"email": email}) or frappe.db.get_value("Patient", {"owner": email})
    if not patient_id:
        return {"message": "I couldn’t find any appointments linked to your account."}

    last_appt = frappe.db.get_all(
        "Make Appointment",
        filters={"patient": patient_id},
        fields=["name", "appointment_date", "appointment_type", "practitioner", "status"],
        order_by="creation desc",
        limit=1
    )

    if not last_appt:
        return {"message": "You don’t have any past appointments yet."}

    appt = last_appt[0]
    return {"message": f"🕓 Your last appointment was a <b>{appt.appointment_type}</b> with <b>{appt.practitioner}</b> on <b>{appt.appointment_date}</b>. Status: <b>{appt.status}</b>."}


def get_upcoming_appointments():
    """Fetches all future appointments for the logged-in patient."""
    email = frappe.session.user
    patient_id = frappe.db.get_value("Patient", {"email": email}) or frappe.db.get_value("Patient", {"owner": email})
    if not patient_id:
        return {"message": "No appointments found for your account."}

    records = frappe.db.get_all(
        "Make Appointment",
        filters={"patient": patient_id, "appointment_date": [">=", nowdate()]},
        fields=["appointment_date", "appointment_type", "practitioner", "status"],
        order_by="appointment_date asc"
    )

    if not records:
        return {"message": "You have no upcoming appointments."}

    message = "📅 <b>Your upcoming appointments:</b><br>"
    for r in records:
        message += f"- {r.appointment_date}: {r.appointment_type} with {r.practitioner} ({r.status})<br>"
    return {"message": message}
