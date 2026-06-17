let editedMessages = null;
let promptMode = "chat";
let summaryUntilMessageId = null;
let chatHistory = [];


// ==========================
// ACTIVE CONVERSATION
// ==========================
function getActiveConversationId() {
    if (window.activeConversationId) {
        return window.activeConversationId;
    }

    const select = document.getElementById("conversationSelect");

    if (!select || !select.value) {
        return null;
    }

    const id = parseInt(select.value, 10);

    if (Number.isNaN(id)) {
        return null;
    }

    window.activeConversationId = id;

    return id;
}


// ==========================
// MODEL
// ==========================
function getSelectedModel() {
    const el = document.getElementById("modelSelect");
    return el ? el.value : "llama-3.1-8b-instant";
}


// ==========================
// HTML / MARKDOWN
// ==========================
function escapeHtml(text) {
    return String(text || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}


function renderMarkdown(text) {
    text = String(text || "");

    if (window.marked) {
        marked.setOptions({
            gfm: true,
            breaks: true
        });

        const dirtyHtml = marked.parse(text);

        let cleanHtml = dirtyHtml;

        if (window.DOMPurify) {
            cleanHtml = DOMPurify.sanitize(
                dirtyHtml,
                {
                    USE_PROFILES: {
                        html: true
                    }
                }
            );
        }

        const wrapper = document.createElement("div");
        wrapper.innerHTML = cleanHtml;

        wrapper.querySelectorAll("table").forEach((table) => {
            if (
                table.parentElement &&
                table.parentElement.classList.contains("table-wrap")
            ) {
                return;
            }

            const tableWrap = document.createElement("div");
            tableWrap.className = "table-wrap";

            table.parentNode.insertBefore(
                tableWrap,
                table
            );

            tableWrap.appendChild(table);
        });

        return wrapper.innerHTML;
    }

    return escapeHtml(text).replace(/\n/g, "<br>");
}


// ==========================
// ERRORS
// ==========================
function showApiErrorPopup(message) {
    alert(
        "Błąd API Groq:\n\n" + String(message || "Nieznany błąd.")
    );
}


// ==========================
// PAYLOAD
// ==========================
function getChatPayload() {
    const input = document.getElementById("msg");
    const contextEl = document.getElementById("contextBox");

    return {
        conversation_id: getActiveConversationId(),
        message: input ? input.value.trim() : "",
        context: contextEl ? contextEl.value : "",
        model: getSelectedModel()
    };
}
