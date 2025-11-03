# # Copyright (c) 2025, chai and contributors
# # For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, get_time
from datetime import timedelta, datetime

class MakeAppointment(Document):
    def before_save(self):
        """This hook runs before the document is saved to the database."""
        self.set_end_time()
        if not self.booking_channel:
            self.booking_channel = "Front-desk"

    def validate(self):
        """This hook runs after before_save and before the document is finally saved."""
        if not self.end_time:
            self.set_end_time()
        
        self.validate_practitioner_availability()

    def set_end_time(self):
        """
        Calculates and sets the end_time. This version is robust and handles
        strings, timedeltas, and time objects to prevent TypeErrors.
        """
        if self.start_time and self.appointment_type:
            duration = frappe.db.get_value("Appointment Type", self.appointment_type, "default_duration_mins") or 30
            start_time_obj = None
            if isinstance(self.start_time, str):
                start_time_obj = get_time(self.start_time)

            elif isinstance(self.start_time, timedelta):
                start_time_obj = (datetime.min + self.start_time).time()

            elif isinstance(self.start_time, datetime.time):
                start_time_obj = self.start_time
            
            if not start_time_obj:
                frappe.log_error("Could not parse start_time in MakeAppointment.set_end_time", "Medinova Error")
                return

            full_start_datetime = datetime.combine(datetime.now().date(), start_time_obj)
            full_end_datetime = full_start_datetime + timedelta(minutes=int(duration))
            self.end_time = full_end_datetime.time()

    def validate_practitioner_availability(self):
        """
        Prevents double-booking by checking for any overlapping appointments.
        """
        if not all([self.practitioner, self.appointment_date, self.start_time, self.end_time]):
            return 

        overlapping_appointment = frappe.db.exists(
            "Make Appointment",
            {
                "practitioner": self.practitioner,
                "appointment_date": self.appointment_date,
                "status": ("!=", "Cancelled"),
                "name": ("!=", self.name),
                "start_time": ("<", self.end_time),
                "end_time": (">", self.start_time),
            }
        )

        if overlapping_appointment:
            frappe.throw(
                f"Practitioner is already booked for this time slot. Conflicting Appointment: {overlapping_appointment}"
            )

