// In the application form, textarea contains \n or \r\n line breaks. Unfortunately,
// most browsers understand \r\n only, so make sure that's how the content is shown:
for (const textareaId in ["id_application", "id_notes"]) {
    let textareaForFixup = document.getElementById(textareaId);
    if (textareaForFixup !== null) {
        textareaForFixup.value = textareaForFixup.value.replace(/\r?\n/g, '\r\n')
    }
}

function toggleTicketNerdDetails() {
    let content = document.getElementById("ticket_nerd_details_contents");
    let toggle = document.getElementById("ticket_nerd_details_toggle");

    if (content === null) return;
    content.classList.toggle("invisible");

    if (toggle === null) return;
    toggle.textContent = content.classList.contains("invisible") ? "[+]" : "[-]";
}

let nerdDetailsLink = document.getElementById("ticket_nerd_details_link");
if (nerdDetailsLink !== null) {
    nerdDetailsLink.onclick = toggleTicketNerdDetails;
}
