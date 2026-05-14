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


function getChatPayload() {

    const input = document.getElementById("msg");
    const contextEl = document.getElementById("contextBox");

    return {
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

    const box = document.getElementById("chat-box");

    const payload = getChatPayload();

    if (!payload.message) return;

    document.getElementById("msg").value = "";

    box.innerHTML += `<div class="user">${payload.message}</div>`;

    const res = await fetch("/chat", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
    });

    const data = await res.json();

    box.innerHTML += `<div class="bot">${formatReply(data.reply)}</div>`;

    chatHistory.push(
        { role: "user", content: payload.message },
        { role: "assistant", content: data.reply }
    );

    box.scrollTop = box.scrollHeight;
}


// ==========================
// POPUP PREVIEW (PROMPT DEBUG + TOKEN ESTIMATE)
// ==========================
async function toggleContext() {

    const modal = document.getElementById("contextModal");

    if (!modal.classList.contains("hidden")) {
        modal.classList.add("hidden");
        return;
    }

    const payload = getChatPayload();

    const res = await fetch("/prompt-context", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
    });

    const data = await res.json();

    document.getElementById("contextContent").textContent = `

===== TOKEN ESTIMATE =====
~${data.tokens_estimate || 0} tokens (approx)


===== SYSTEM PROMPT =====

${data.system_prompt || ""}


===== CONTEXT =====

${data.context || ""}


===== HISTORY =====

${JSON.stringify(data.history || [], null, 2)}


===== USER MESSAGE =====

${data.user_message || ""}


===== FINAL MESSAGES =====

${JSON.stringify(data.messages || [], null, 2)}

`;

    modal.classList.remove("hidden");
}


// ==========================
// INIT
// ==========================
document.addEventListener("DOMContentLoaded", () => {

    const input = document.getElementById("msg");

    loadModels();

    if (!input) return;

    input.addEventListener("keydown", (e) => {

        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMsg();
        }
    });

});
