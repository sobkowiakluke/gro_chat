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

async function sendMsg() {

    const input = document.getElementById("msg");
    const box = document.getElementById("chat-box");
    const contextEl = document.getElementById("contextBox");

    const message = input.value.trim();
    if (!message) return;

    input.value = "";

    box.innerHTML += `<div class="user">${message}</div>`;

    const res = await fetch("/chat", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({
            message,
            model: getSelectedModel(),
            context: contextEl.value,
            history: chatHistory.slice(-10)
        })
    });

    const data = await res.json();

    box.innerHTML += `<div class="bot">${formatReply(data.reply)}</div>`;

    chatHistory.push(
        { role: "user", content: message },
        { role: "assistant", content: data.reply }
    );

    box.scrollTop = box.scrollHeight;
    contextEl.value = "";
}
