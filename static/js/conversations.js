window.activeConversationId = null;
window.conversations = [];


function syncChatHistoryFromMessages(messages) {

    if (typeof chatHistory === "undefined") {
        return;
    }

    chatHistory = [];

    messages.forEach((msg) => {

        if (
            msg.role === "user" ||
            msg.role === "assistant"
        ) {
            chatHistory.push({
                role: msg.role,
                content: msg.content
            });
        }
    });
}


function renderAssistantMessage(content) {

    if (typeof renderMarkdown === "function") {
        return renderMarkdown(content);
    }

    if (typeof escapeHtml === "function") {
        return escapeHtml(content).replace(/\n/g, "<br>");
    }

    return String(content || "");
}


function renderUserMessage(content) {

    if (typeof escapeHtml === "function") {
        return escapeHtml(content);
    }

    return String(content || "");
}


function renderConversationMessages(messages) {

    const box =
        document.getElementById("chat-box");

    if (!box) {
        return;
    }

    box.innerHTML = "";

    messages.forEach((msg) => {

        if (msg.role === "user") {

            box.innerHTML += `
                <div class="user">
                    ${renderUserMessage(msg.content)}
                </div>
            `;

        } else if (msg.role === "assistant") {

            box.innerHTML += `
                <div class="bot">
                    ${renderAssistantMessage(msg.content)}
                </div>
            `;
        }
    });

    box.scrollTop = box.scrollHeight;
}


async function loadConversationMessages(conversationId) {

    if (!conversationId) {
        syncChatHistoryFromMessages([]);
        renderConversationMessages([]);
        return;
    }

    const res =
        await fetch(
            `/conversations/${conversationId}/messages`
        );

    const data =
        await res.json();

    const messages =
        data.messages || [];

    syncChatHistoryFromMessages(messages);

    renderConversationMessages(messages);
}


async function loadConversations() {

    const select =
        document.getElementById(
            "conversationSelect"
        );

    if (!select) {
        return;
    }

    const previousId =
        window.activeConversationId;

    const res =
        await fetch("/conversations");

    const data =
        await res.json();

    window.conversations =
        data.conversations || [];

    select.innerHTML = "";

    if (window.conversations.length === 0) {

        const option =
            document.createElement("option");

        option.value = "";
        option.textContent =
            "Brak chatu";

        select.appendChild(option);

        window.activeConversationId = null;

        await loadConversationMessages(null);

        if (typeof schedulePromptTokenEstimateUpdate === "function") {
            schedulePromptTokenEstimateUpdate();
        }

        return;
    }

    window.conversations.forEach((conv) => {

        const option =
            document.createElement("option");

        option.value = conv.id;
        option.textContent =
            conv.title || `Chat ${conv.id}`;

        select.appendChild(option);
    });

    const stillExists =
        previousId &&
        window.conversations.some(
            conv => conv.id === previousId
        );

    const selectedId =
        stillExists
            ? previousId
            : window.conversations[0].id;

    select.value = selectedId;

    window.activeConversationId = selectedId;

    await loadConversationMessages(
        selectedId
    );

    if (typeof schedulePromptTokenEstimateUpdate === "function") {
        schedulePromptTokenEstimateUpdate();
    }
}


async function createConversationFromHeader() {

    const title =
        prompt(
            "Nazwa chatu",
            "Nowy chat"
        );

    if (title === null) {
        return;
    }

    const res =
        await fetch(
            "/conversations",
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json"
                },
                body: JSON.stringify({
                    title: title.trim() || "Nowy chat"
                })
            }
        );

    const data =
        await res.json();

    window.activeConversationId =
        data.id;

    await loadConversations();
}


async function deleteActiveConversation() {

    if (!window.activeConversationId) {
        alert("Nie wybrano chatu.");
        return;
    }

    if (
        !confirm(
            "Usunąć aktywny chat?"
        )
    ) {
        return;
    }

    await fetch(
        `/conversations/${window.activeConversationId}`,
        {
            method: "DELETE"
        }
    );

    window.activeConversationId = null;

    await loadConversations();
}


document.addEventListener(
    "DOMContentLoaded",
    () => {

        const select =
            document.getElementById(
                "conversationSelect"
            );

        if (select) {

            select.addEventListener(
                "change",
                async () => {

                    const value =
                        select.value;

                    window.activeConversationId =
                        value
                            ? parseInt(value, 10)
                            : null;

                    await loadConversationMessages(
                        window.activeConversationId
                    );

                    if (typeof schedulePromptTokenEstimateUpdate === "function") {
                        schedulePromptTokenEstimateUpdate();
                    }
                }
            );
        }

        loadConversations();
    }
);
