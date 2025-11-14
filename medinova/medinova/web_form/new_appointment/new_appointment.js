frappe.ready(function () {

    console.log("🩺 New Appointment Webform loaded");

    // === Auto-fetch patient contact and email ===
    frappe.web_form.on('patient', () => {
        const patient = frappe.web_form.get_value('patient');
        if (!patient) {
            frappe.web_form.set_value('patient_contact', '');
            frappe.web_form.set_value('email', '');
            return;
        }

        console.log("Fetching patient details for:", patient);

        frappe.call({
            method: "medinova.medinova.web_form.new_appointment.new_appointment.get_patient_details",
            args: { patient },
            callback: function (r) {
                console.log("Patient details response:", r.message);
                if (r.message) {
                    frappe.web_form.set_value('patient_contact', r.message.patient_contact || '');
                    frappe.web_form.set_value('email', r.message.email || '');
                }
            }
        });
    });

    // === Trigger slot fetching when key fields change ===
    ['practitioner', 'appointment_date', 'appointment_type'].forEach(field => {
        frappe.web_form.on(field, show_available_slots);
    });

    function show_available_slots() {
        const practitioner = frappe.web_form.get_value('practitioner');
        const appointment_date = frappe.web_form.get_value('appointment_date');
        const appointment_type = frappe.web_form.get_value('appointment_type');

        console.log("Fetching slots for:", { practitioner, appointment_date, appointment_type });

        // ✅ Update this selector with your actual HTML fieldname in Frappe
        const wrapper = $('[data-fieldname="available_slots_display"], [data-fieldname="available_slots"], [data-fieldname="slots_section"]');
        wrapper.html('');

        if (!(practitioner && appointment_date && appointment_type)) {
            console.warn("❌ Missing field(s) for slot fetching");
            return;
        }

        frappe.call({
            method: "medinova.medinova.web_form.new_appointment.new_appointment.get_available_slots",
            args: { practitioner, appointment_date, appointment_type },
            freeze: true,
            freeze_message: "Loading available slots...",
            callback: function (r) {
                console.log("🕒 Slots API Response:", r.message);
                const slots = r.message || [];
                if (!slots.length) {
                    wrapper.html('<div class="alert alert-warning mt-2">No slots available for this date.</div>');
                    return;
                }

                let html = `<div class="mt-2"><label><b>Available Slots:</b></label><br>`;
                slots.forEach(slot => {
                    html += `<button class="btn btn-outline-primary btn-sm slot-btn" data-slot="${slot}" style="margin:4px;">${slot}</button>`;
                });
                html += `</div>`;
                wrapper.html(html);

                wrapper.off('click', '.slot-btn').on('click', '.slot-btn', function () {
                    const selected = $(this).data('slot');
                    frappe.web_form.set_value('start_time', selected);
                    calculate_end_time();

                    $('.slot-btn').removeClass('btn-success').addClass('btn-outline-primary');
                    $(this).removeClass('btn-outline-primary').addClass('btn-success');
                });
            }
        });
    }

    // === Auto-calculate end time ===
    frappe.web_form.on('start_time', calculate_end_time);

    function calculate_end_time() {
        const start_time = frappe.web_form.get_value('start_time');
        const appointment_type = frappe.web_form.get_value('appointment_type');
        if (!(start_time && appointment_type)) return;

        frappe.call({
            method: "medinova.medinova.web_form.new_appointment.new_appointment.calculate_end_time",
            args: { start_time, appointment_type },
            callback: function (r) {
                console.log("🧮 End time calculation result:", r.message);
                if (r.message) frappe.web_form.set_value('end_time', r.message);
            }
        });
    }

    // === Restrict past dates ===
    const date_field = frappe.web_form.get_field('appointment_date');
    if (date_field && date_field.$input) {
        date_field.$input.attr('min', frappe.datetime.get_today());
    }

});

