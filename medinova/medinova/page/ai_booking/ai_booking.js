// frappe.pages['ai-booking'].on_page_load = function(wrapper) {
// 	var page = frappe.ui.make_app_page({
// 		parent: wrapper,
// 		title: 'AI Booking',
// 		single_column: true
// 	});
// }
frappe.pages['ai-booking'].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'AI Booking',
        single_column: true
    });

    $(wrapper).find('.page-content').html(frappe.render_template('ai_booking'));

    const chat_messages = $("#chat-messages");
    const chat_input = $("#chat-input");
    const send_button = $("#chat-send");

    let conversation_history = [];
    let confirmed_entities = {};

    function add_message(message_text, sender, type = 'text') {
        let bubble_html = '';

        if (type === 'text') {
            bubble_html = `<div class="message-bubble">${message_text}</div>`;
        } else if (type === 'slots') {
            const buttons_html = message_text.slots.map(slot =>
                `<button class="btn btn-sm slot-btn" data-slot="${slot}">${slot}</button>`
            ).join('');

            bubble_html = `
                <div class="message-bubble">
                    I found these slots for <b>${message_text.entities.practitioner}</b> on <b>${message_text.entities.appointment_date}</b>:
                    <div class="slot-options">${buttons_html}</div>
                </div>`;
            confirmed_entities = message_text.entities;
        }

        const message_html = `<div class="message ${sender}">${bubble_html}</div>`;
        chat_messages.append(message_html);
        chat_messages.scrollTop(chat_messages[0].scrollHeight);
    }

    async function send_chat_message() {
        const message = chat_input.val().trim();
        if (!message) return;

        add_message(message, 'user');
        conversation_history.push(`User: ${message}`);
        chat_input.val('');

        add_message("...", 'bot');

        const response = await frappe.call({
            method: 'medinova.api.get_slots_from_natural_language',
            args: {
                message: message,
                conversation_history: JSON.stringify(conversation_history)
            }
        });

        chat_messages.find(".message.bot").last().remove();
        const result = response.message || {};

        if (result.error) {
            add_message(result.error, 'bot');
        } else if (result.slots) {
            add_message(result, 'bot', 'slots');
        } else if (result.message) {
            add_message(result.message, 'bot');
        } else {
            add_message("I’m sorry, I didn’t understand that.", 'bot');
        }

        conversation_history.push(`Bot: ${JSON.stringify(result)}`);
    }

    send_button.on("click", send_chat_message);
    chat_input.on("keypress", function (e) {
        if (e.which === 13) send_chat_message();
    });

    chat_messages.on("click", ".slot-btn", async function () {
        const selected_time = $(this).data("slot");
        add_message(`I'll take ${selected_time}, please.`, 'user');

        const patient_name = frappe.session.user_fullname;

        const booking_response = await frappe.call({
            method: 'medinova.api.create_appointment_from_chat',
            args: {
                patient_name: patient_name,
                practitioner: confirmed_entities.practitioner,
                appointment_date: confirmed_entities.appointment_date,
                start_time: selected_time,
                appointment_type: confirmed_entities.appointment_type
            }
        });

        const result = booking_response.message;
        if (result.success) {
            add_message(result.message, 'bot');
        } else {
            add_message(result.error, 'bot');
        }
    });

    add_message("👋 Hello! How can I help you today?<br>Try asking:<br>- 'Book dental checkup on Monday'<br>- 'Show my last appointment'<br>- 'List my upcoming appointments'", 'bot');
};
