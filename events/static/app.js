// In the application form, textarea contains \n or \r\n line breaks. Unfortunately,
// most browsers understand \r\n only, so make sure that's how the content is shown:
for (const textareaId in ["id_application", "id_notes"]) {
    let textareaForFixup = document.getElementById(textareaId);
    if (textareaForFixup !== null) {
        textareaForFixup.value = textareaForFixup.value.replace(/\r?\n/g, '\r\n')
    }
}
