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
    let finalPromptSections = null;
    let messageToSaveAndDisplay = basePayload.message;

    if (promptPopupIsOpen) {
        finalPromptSections = buildPromptSectionsFromEditors();
        finalMessages = buildMessagesFromPromptSections();

        const editedUserMessage = finalPromptSections.user_message;

        if (editedUserMessage) {
            messageToSaveAndDisplay = editedUserMessage;
        }

        if (!finalMessages.length) {
            alert("Prompt jest pusty.");
            return;
        }

        if (!messageToSaveAndDisplay && promptMode !== "summary") {
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

    if (finalPromptSections) {
        payload.prompt_sections = finalPromptSections;
        payload.persist_prompt_memory = promptMemoryDirty;
        payload.prompt_memory_overrides = getPromptMemoryOverrides();
    } else if (finalMessages) {
        payload.messages = finalMessages;
    }

    if (finalMessages && promptMode === "summary") {
        payload.summary_mode = true;
        payload.summary_until_message_id = summaryUntilMessageId;
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

    if (promptMode === "summary" || data.summary_updated) {
        setPromptTextareaValue(
            "promptSummary",
            data.summary || ""
        );

        editedMessages = null;
        setPromptEditorKind("chat");
        summaryUntilMessageId = null;
        promptMemoryDirty = false;
        updatePromptMeta(data);
        schedulePromptTokenEstimateUpdate();

        const remaining = Number(data.summary_messages_remaining || 0);
        alert(
            remaining > 0
                ? `Summary porcji zostało zapisane. Pozostało ${remaining} wiadomości; użyj ponownie History → Summary.`
                : "Summary zostało zapisane i obejmuje całą oczekującą historię."
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
    promptMemoryDirty = false;

    clearPromptSectionEditors();
    closeContextModal();
    schedulePromptTokenEstimateUpdate();
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
    setPromptEditorKind("chat");
    summaryUntilMessageId = null;

    if (data.prompt_sections) {
        fillPromptSectionEditorsFromSections(data.prompt_sections);
    } else {
        fillPromptSectionEditors(editedMessages);
    }

    updatePromptMeta(data);
}

// ==========================
// POPUP PREVIEW
// ==========================
async function closeContextModal() {
    const modal = document.getElementById("contextModal");

    if (promptMode !== "summary" && promptMemoryDirty) {
        const shouldSave = confirm(
            "Prompt został zmodyfikowany. Zapisać zmiany jako pamięć tej rozmowy?"
        );

        if (shouldSave) {
            const saved = await savePromptMemoryFromPopup();

            if (!saved) {
                return;
            }
        } else {
            promptMemoryDirty = false;
        }
    }

    if (modal) {
        modal.classList.add("hidden");
    }

    if (promptMode === "summary") {
        setPromptEditorKind("chat");
        summaryUntilMessageId = null;
        editedMessages = null;
    }

    // Nie czyścimy promptu przy zamknięciu zwykłego promptu.
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

    const modal = document.getElementById("contextModal");
    const popupIsOpen = modal && !modal.classList.contains("hidden");

    if (popupIsOpen && typeof buildPromptSectionsFromEditors === "function") {
        payload.prompt_sections = buildPromptSectionsFromEditors();
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
                data.prompt_over_budget
                    ? `tokeny: ${estimate} / ${budget} — PRZEKROCZONO`
                    : `tokeny: ${estimate} / ${budget}`
            );
        } else if (estimate !== null) {
            setPromptTokenEstimate(
                `tokeny: ${estimate}`
            );
        } else {
            setPromptTokenEstimate("tokeny: —");
        }

        if (popupIsOpen && typeof updatePromptMeta === "function") {
            updatePromptMeta(data);
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
