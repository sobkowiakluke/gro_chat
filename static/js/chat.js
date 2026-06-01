let editedMessages = null;
let chatHistory = [];


function getActiveConversationId() {
    if (window.activeConversationId) {
        return window.activeConversationId;
    }

    const select =
        document.getElementById("conversationSelect");

    if (!select || !select.value) {
        return null;
    }

    const id =
        parseInt(select.value, 10);

    if (Number.isNaN(id)) {
        return null;
    }

    window.activeConversationId = id;

    return id;
}


function getSelectedModel() {
    const el = document.getElementById("modelSelect");
    return el ? el.value : "llama-3.1-8b-instant";
}


function escapeHtml(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}


function formatReply(text) {

    text = text.replace(/```([\s\S]*?)```/g, (_, code) =>
        `<pre><code>${escapeHtml(code.trim())}</code></pre>`
    );

    text = text.replace(/`([^`]+)`/g, (_, code) =>
        `<code class="inline-code">${escapeHtml(code)}</code>`
    );

    return text.replace(/\n/g, "<br>");
}


// ==========================
// BUILD BASE PAYLOAD
// ==========================
function getChatPayload() {

    const input = document.getElementById("msg");
    const contextEl = document.getElementById("contextBox");

    return {
        conversation_id: getActiveConversationId(),
        message: input.value.trim(),
        context: contextEl.value,
        history: chatHistory.slice(-10),
        model: getSelectedModel()
    };
}


// ==========================
// SEND MESSAGE
// ==========================
async function sendMsg() {

    const conversationId =
        getActiveConversationId();

    if (!conversationId) {
        alert("Najpierw utwórz albo wybierz chat.");
        return;
    }

    const box = document.getElementById("chat-box");

    const basePayload = getChatPayload();

    if (!basePayload.message) return;

    let finalMessages = editedMessages;

    const contextEditor =
        document.getElementById("contextContent");

    if (contextEditor && contextEditor.value.trim()) {

        try {

            finalMessages = JSON.parse(
                contextEditor.value
            );

        } catch (e) {

            alert("Błąd JSON w popupie promptu");
            return;
        }
    }

    if (!finalMessages) {

        const previewRes = await fetch(
            "/prompt-context",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(basePayload)
            }
        );

        const previewData =
            await previewRes.json();

        finalMessages =
            previewData.messages;
    }

    document.getElementById("msg").value = "";

    box.innerHTML += `
        <div class="user">
            ${escapeHtml(basePayload.message)}
        </div>
    `;

    const payload = {
        conversation_id: conversationId,
        model: basePayload.model,
        messages: finalMessages
    };

    const res = await fetch("/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
    });

    const data = await res.json();

    box.innerHTML += `
        <div class="bot">
            ${formatReply(data.reply)}
        </div>
    `;

    chatHistory.push(
        {
            role: "user",
            content: basePayload.message
        },
        {
            role: "assistant",
            content: data.reply
        }
    );

    editedMessages = null;

    box.scrollTop = box.scrollHeight;
}


// ==========================
// POPUP PREVIEW
// ==========================
async function toggleContext() {

    const conversationId =
        getActiveConversationId();

    if (!conversationId) {
        alert("Najpierw utwórz albo wybierz chat.");
        return;
    }

    const modal =
        document.getElementById("contextModal");

    if (!modal.classList.contains("hidden")) {
        modal.classList.add("hidden");
        return;
    }

    const payload = getChatPayload();

    const res = await fetch(
        "/prompt-context",
        {
            method: "POST",
            headers: {
                "Content-Type":
                    "application/json"
            },
            body: JSON.stringify(payload)
        }
    );

    const data = await res.json();

    editedMessages = data.messages;

    document.getElementById(
        "contextContent"
    ).value = JSON.stringify(
        data.messages,
        null,
        2
    );

    modal.classList.remove("hidden");
}


// ==========================
// INIT
// ==========================
document.addEventListener(
    "DOMContentLoaded",
    () => {

        const input =
            document.getElementById("msg");

        loadModels();

        if (!input) return;

        input.addEventListener(
            "keydown",
            (e) => {

                if (
                    e.key === "Enter" &&
                    !e.shiftKey
                ) {
                    e.preventDefault();
                    sendMsg();
                }
            }
        );

    }
);
