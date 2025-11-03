// // Copyright (c) 2025, chai and contributors
// // For license information, please see license.txt

frappe.ui.form.on('Make Appointment', {
    refresh: function(frm) {
        if (frm.get_field('appointment_date').datepicker) {
            frm.get_field('appointment_date').datepicker.update({
                minDate: new Date()
            });
        }

        if (frm.is_new()) {
            let slot_display_wrapper = frm.fields_dict.available_slots_display.$wrapper;
            slot_display_wrapper.html('');
        }
    },

    patient: function(frm) {
        if (frm.doc.patient) {
            frappe.db.get_value('Patient', frm.doc.patient, 'contact_number')
                .then(r => {
                    if (r.message && r.message.contact_number) {
                        frm.set_value('patient_contact', r.message.contact_number);
                    }
                });
        } else {
            frm.set_value('patient_contact', '');
        }
    },

    practitioner: function(frm) {
        get_available_start_times(frm);
    },
    appointment_date: function(frm) {
        get_available_start_times(frm);
    },
    appointment_type: function(frm) {
        get_available_start_times(frm);
    }
});

function get_available_start_times(frm) {
    frm.set_value('start_time', null);
    frm.set_value('end_time', null);
    let slot_display_wrapper = frm.fields_dict.available_slots_display.$wrapper;
    slot_display_wrapper.html('');

    if (frm.doc.practitioner && frm.doc.appointment_date && frm.doc.appointment_type) {
        frm.dashboard.show_progress('Checking Schedule', 'Finding available times...');

        frappe.call({
            method: "medinova.api.get_available_start_times",
            args: {
                practitioner: frm.doc.practitioner,
                appointment_date: frm.doc.appointment_date,
                appointment_type: frm.doc.appointment_type
            },
            callback: function(r) {
                frm.dashboard.hide_progress();
                if (r.message && r.message.available_slots) {
                    const slots = r.message.available_slots;
                    if (slots.length > 0) {
                        let html = `<div><label>Click an available start time:</label></div>`;
                        slots.forEach(slot => {
                            html += `<button class="btn btn-default btn-sm slot-btn" 
                                            style="margin: 0 5px 5px 0;" 
                                            data-slot-time="${slot}">
                                        ${slot}
                                    </button>`;
                        });
                        slot_display_wrapper.html(html);

                        slot_display_wrapper.on('click', '.slot-btn', function() {
                            const selected_time = $(this).data('slot-time');
                            frm.set_value('start_time', selected_time);
                            calculate_and_set_end_time(frm);
                            slot_display_wrapper.find('.slot-btn').removeClass('btn-success').addClass('btn-default');
                            $(this).removeClass('btn-default').addClass('btn-success');
                        });
                    } else {
                        let no_slots_html = `<div class="alert alert-warning">No time slots are available for this service on the selected date.</div>`;
                        slot_display_wrapper.html(no_slots_html);
                    }
                }
            }
        });
    }
}

function calculate_and_set_end_time(frm) {
    if (frm.doc.start_time && frm.doc.appointment_type) {
        frappe.db.get_value('Appointment Type', frm.doc.appointment_type, 'default_duration_mins')
            .then(r => {
                if (r.message && r.message.default_duration_mins) {
                    let duration = r.message.default_duration_mins;
                    let end_time_str = moment(frm.doc.start_time, 'HH:mm:ss')
                                        .add(duration, 'minutes')
                                        .format('HH:mm:ss');
                    frm.set_value('end_time', end_time_str);
                }
            });
    }
}

