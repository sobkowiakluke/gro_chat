async function sendMsg() {
    const conversationId = getActiveConversationId();

    if (!conversationId) {
        alert("Najpierw utwórz albo wybierz chat.");
        return;
    }

    const box = document.getElementById("chat-box");
    const input = document.getElementById("msg");

    const basePayload = getChatPayload();

    const contextModal = document.getElementById("contextModal");

    const promptPopupIsOpen = (
        contextModal &&
        !contextModal.classList.contains("hidden")
    );

    let finalMessages = null;
    let messageToSaveAndDisplay = basePayload.message;

    if (promptPopupIsOpen) {
        finalMessages = buildMessagesFromPromptSections();

        const editedUserMessage = getUserMessageFromPromptSections();

        if (editedUserMessage) {
            messageToSaveAndDisplay = editedUserMessage;
        }

        if (!finalMessages.length) {
            alert("Prompt jest pusty.");
            return;
        }

        if (!messageToSaveAndDisplay) {
            alert("Brak wiadomości USER MESSAGE w prompcie.");
            return;
        }

    } else {
        if (!basePayload.message) {
            return;
        }
    }

    const payload = {
        conversation_id: conversationId,
        model: basePayload.model,
        message: messageToSaveAndDisplay,
        context: basePayload.context
    };

    if (finalMessages) {
        payload.messages = finalMessages;
    }

    let res;
    let data;

    try {
        res = await fetch(
            "/chat",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(payload)
            }
        );

        data = await res.json();

    } catch (e) {
        showApiErrorPopup(
            "Nie udało się połączyć z backendem Flask.\n" +
            String(e)
        );

        return;
    }

    if (!res.ok) {
        showApiErrorPopup(
            data.error ||
            data.reply ||
            "Nieznany błąd API."
        );

        return;
    }

    if (input) {
        input.value = "";
    }

    if (box) {
        box.innerHTML += `
            <div class="user">
                ${escapeHtml(messageToSaveAndDisplay)}
            </div>
        `;

        box.innerHTML += `
            <div class="bot">
                ${renderMarkdown(data.reply)}
            </div>
        `;

        box.scrollTop = box.scrollHeight;
    }

    chatHistory.push(
        {
            role: "user",
            content: messageToSaveAndDisplay
        },
        {
            role: "assistant",
            content: data.reply
        }
    );

    editedMessages = null;

    clearPromptSectionEditors();
    closeContextModal();
}
async function toggleContext() {
    const modal = document.getElementById("contextModal");

    if (!modal) {
        alert("Brak elementu contextModal w HTML.");
        return;
    }

    if (!modal.classList.contains("hidden")) {
        closeContextModal();
        return;
    }

    // Najpierw otwieramy popup.
    // Dzięki temu klik zawsze daje widoczny efekt.
    modal.classList.remove("hidden");

    const conversationId = getActiveConversationId();

    if (!conversationId) {
        alert("Najpierw utwórz albo wybierz chat.");
        return;
    }

    const payload = getChatPayload();

    let res;
    let data;

    try {
        res = await fetch(
            "/prompt-context",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(payload)
            }
        );

        data = await res.json();

    } catch (e) {
        alert(
            "Nie udało się pobrać podglądu promptu.\n\n" +
            String(e)
        );

        return;
    }

    if (!res.ok) {
        alert(
            data.error ||
            "Nie udało się pobrać podglądu promptu."
        );

        return;
    }

    if (!Array.isArray(data.messages)) {
        alert("Backend nie zwrócił pola messages dla popupu.");
        return;
    }

    editedMessages = data.messages;

    fillPromptSectionEditors(
        editedMessages
    );

    updatePromptMeta(data);
}

// ==========================
// POPUP PREVIEW
// ==========================
function closeContextModal() {
    const modal = document.getElementById("contextModal");

    if (modal) {
        modal.classList.add("hidden");
    }

    // Nie czyścimy promptu przy zamknięciu.
}

// ==========================
// TOKEN ESTIMATE
// ==========================
let tokenEstimateTimer = null;


function setPromptTokenEstimate(text) {
    const el = document.getElementById("promptTokenEstimate");

    if (el) {
        el.innerText = text;
    }
}


async function updatePromptTokenEstimate() {
    const payload = getChatPayload();

    if (!payload.conversation_id) {
        setPromptTokenEstimate("tokeny: —");
        return;
    }

    try {
        const res = await fetch(
            "/prompt-context",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(payload)
            }
        );

        const data = await res.json();

        if (!res.ok) {
            setPromptTokenEstimate("tokeny: błąd");
            return;
        }

        const estimate = data.tokens_estimate ?? null;
        const budget = data.token_budget ?? null;

        if (estimate !== null && budget !== null) {
            setPromptTokenEstimate(
                `tokeny: ${estimate} / ${budget}`
            );
        } else if (estimate !== null) {
            setPromptTokenEstimate(
                `tokeny: ${estimate}`
            );
        } else {
            setPromptTokenEstimate("tokeny: —");
        }

    } catch (e) {
        setPromptTokenEstimate("tokeny: błąd");
    }
}


function schedulePromptTokenEstimateUpdate() {
    clearTimeout(tokenEstimateTimer);

    tokenEstimateTimer = setTimeout(
        updatePromptTokenEstimate,
        500
    );
}
