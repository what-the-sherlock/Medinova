// Copyright (c) 2025, chai and contributors
// For license information, please see license.txt

frappe.ui.form.on('Patient Encounter', {
    refresh: function(frm) {
        console.log("Refresh event fired.");
        console.log("Is New:", frm.is_new()); 
        console.log("Docstatus:", frm.doc.docstatus);

        if (!frm.is_new() && frm.doc.docstatus === 0) {
            console.log("Conditions met! Attempting to add buttons..."); 

            frm.clear_custom_buttons();
            if (frm.doc.grand_total == null || frm.doc.grand_total == 0) { 
                frm.add_custom_button(__('Generate Bill'), function() {
                    frappe.call({
                        method: 'medinova.api.calculate_encounter_bill',
                        args: {
                            encounter_name: frm.doc.name
                        },
                        freeze: true,
                        freeze_message: __('Calculating total bill...'),
                        callback: function(r) {
                            if (r.message) {
                                frappe.show_alert({
                                    message: __('Bill generated successfully. Grand Total: {0}', [format_currency(r.message.grand_total)]),
                                    indicator: 'green'
                                });
                                frm.reload_doc(); 
                            }
                        }
                    });
                }).addClass('btn-primary');
            }

            if (frm.doc.grand_total > 0 && frm.doc.payment_status === 'Pending') {
                frm.add_custom_button(__('Process Payment'), function() { 
                    frappe.confirm(
                        'Process payment of ' + format_currency(frm.doc.grand_total) + '?',
                        () => {
                            frappe.call({
                                method: 'medinova.api.process_mock_payment',
                                args: { encounter_name: frm.doc.name },
                                callback: function(r) {
                                     if (r.message && r.message.payment_name) {
                                        frappe.set_route('Form', 'Encounter Payment', r.message.payment_name);
                                    }
                                }
                            });
                        }
                    );
                }).addClass('btn-success');
            }
        } else {
             console.log("Conditions NOT met for adding buttons.");
             if(frm.is_new()) {
                 console.log("Reason: Document is new (unsaved).");
             }
             if(frm.doc.docstatus !== 0) {
                 console.log("Reason: Document status is not Draft (0). It is:", frm.doc.docstatus);
             }
        }
    }
});