let editedMessages = null;
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


// ==========================
// PROMPT SECTIONS
// ==========================
function getPromptTextareaValue(id) {
    const el = document.getElementById(id);
    return el ? el.value : "";
}


function setPromptTextareaValue(id, value) {
    const el = document.getElementById(id);

    if (el) {
        el.value = value || "";
    }
}


function clearPromptSectionEditors() {
    setPromptTextareaValue("promptSystem", "");
    setPromptTextareaValue("promptSummary", "");
    setPromptTextareaValue("promptContext", "");
    setPromptTextareaValue("promptUser", "");

    const historyList = document.getElementById("promptHistory");

    if (historyList) {
        historyList.innerHTML = "";
    }

    const meta = document.getElementById("promptMeta");

    if (meta) {
        meta.innerText = "";
    }
}
function clearPromptAfterSendKeepSummary() {
    setPromptTextareaValue("promptSystem", "");
    setPromptTextareaValue("promptContext", "");
    setPromptTextareaValue("promptUser", "");

    const historyList = document.getElementById("promptHistory");

    if (historyList) {
        historyList.innerHTML = "";
    }

    const meta = document.getElementById("promptMeta");

    if (meta) {
        meta.innerText = "";
    }

    // promptSummary zostaje bez zmian
}

function addHistoryEditor(role, content) {
    const historyList = document.getElementById("promptHistory");

    if (!historyList) {
        return;
    }

    const item = document.createElement("div");
    item.className = "prompt-history-item";

    item.innerHTML = `
        <div class="prompt-history-top">
            <select class="prompt-history-role">
                <option value="user">user</option>
                <option value="assistant">assistant</option>
                <option value="system">system</option>
            </select>

            <button type="button" onclick="this.closest('.prompt-history-item').remove()">
                Usuń
            </button>
        </div>

        <textarea
            class="prompt-history-content"
            spellcheck="false"
        ></textarea>
    `;

    const roleSelect = item.querySelector(".prompt-history-role");
    const contentTextarea = item.querySelector(".prompt-history-content");

    roleSelect.value = role || "user";
    contentTextarea.value = content || "";

    historyList.appendChild(item);
}


function getHistoryMessagesFromEditors() {
    const historyList = document.getElementById("promptHistory");

    if (!historyList) {
        return [];
    }

    const items = historyList.querySelectorAll(".prompt-history-item");
    const messages = [];

    items.forEach((item) => {
        const roleEl = item.querySelector(".prompt-history-role");
        const contentEl = item.querySelector(".prompt-history-content");

        const role = roleEl ? roleEl.value : "user";
        const content = contentEl ? contentEl.value.trim() : "";

        if (!content) {
            return;
        }

        messages.push({
            role: role,
            content: content
        });
    });

    return messages;
}


function splitMessagesIntoSections(messages) {
    const sections = {
        system: [],
        summary: [],
        context: [],
        history: [],
        user: ""
    };

    if (!Array.isArray(messages)) {
        return sections;
    }

    messages.forEach((msg, index) => {
        const role = msg.role || "";
        const content = msg.content || "";

        if (
            role === "system" &&
            content.startsWith("STRESZCZENIE")
        ) {
            sections.summary.push(content);
            return;
        }

        if (
            role === "system" &&
            content.startsWith("KONTEKST:")
        ) {
            sections.context.push(
                content.replace(/^KONTEKST:\n?/, "")
            );
            return;
        }

        if (role === "system") {
            sections.system.push(content);
            return;
        }

        if (
            role === "user" &&
            index === messages.length - 1
        ) {
            sections.user = content;
            return;
        }

        sections.history.push({
            role: role,
            content: content
        });
    });

    return sections;
}


function fillPromptSectionEditors(messages) {
    clearPromptSectionEditors();

    const sections = splitMessagesIntoSections(messages);

    setPromptTextareaValue(
        "promptSystem",
        sections.system.join("\n\n---\n\n")
    );

    setPromptTextareaValue(
        "promptSummary",
        sections.summary.join("\n\n---\n\n")
    );

    setPromptTextareaValue(
        "promptContext",
        sections.context.join("\n\n---\n\n")
    );

    setPromptTextareaValue(
        "promptUser",
        sections.user
    );

    sections.history.forEach((msg) => {
        addHistoryEditor(
            msg.role,
            msg.content
        );
    });
}


function buildMessagesFromPromptSections() {
    const messages = [];

    const system = getPromptTextareaValue("promptSystem").trim();
    const summary = getPromptTextareaValue("promptSummary").trim();
    const context = getPromptTextareaValue("promptContext").trim();
    const user = getPromptTextareaValue("promptUser").trim();

    if (system) {
        system
            .split(/\n---\n/g)
            .map((x) => x.trim())
            .filter(Boolean)
            .forEach((content) => {
                messages.push({
                    role: "system",
                    content: content
                });
            });
    }

    if (summary) {
        messages.push({
            role: "system",
            content: summary
        });
    }

    if (context) {
        messages.push({
            role: "system",
            content: "KONTEKST:\n" + context
        });
    }

    getHistoryMessagesFromEditors().forEach((msg) => {
        messages.push(msg);
    });

    if (user) {
        messages.push({
            role: "user",
            content: user
        });
    }

    return messages;
}


function getUserMessageFromPromptSections() {
    return getPromptTextareaValue("promptUser").trim();
}


function updatePromptMeta(data) {
    const meta = document.getElementById("promptMeta");

    if (!meta) {
        return;
    }

    const parts = [];

    if (data.tokens_estimate !== undefined && data.token_budget !== undefined) {
        parts.push(
            `tokeny: ${data.tokens_estimate} / ${data.token_budget}`
        );
    }

    if (data.history_limit !== undefined && data.history_limit !== null) {
        parts.push(
            `historia: ${data.history_limit}`
        );
    }

    if (data.summary_token_limit !== undefined && data.summary_token_limit !== null) {
        parts.push(
            `summary limit: ${data.summary_token_limit}`
        );
    }

    if (data.summary_was_trimmed) {
        parts.push("summary przycięte");
    }

    meta.innerText = parts.join(" | ");
}


// ==========================
// COMPRESS HISTORY TO SUMMARY
// ==========================
async function compressHistoryToSummary() {
    const historyMessages = getHistoryMessagesFromEditors();

    if (!historyMessages.length) {
        alert("Brak historii do streszczenia.");
        return;
    }

    const model = getSelectedModel();
    const previousSummary = getPromptTextareaValue("promptSummary");

    let res;
    let data;

    try {
        res = await fetch("/compress-history", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                model: model,
                messages: historyMessages,
                summary: previousSummary
            })
        });

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
            "Nie udało się utworzyć summary."
        );

        return;
    }

    setPromptTextareaValue(
        "promptSummary",
        data.summary || ""
    );

    const historyList = document.getElementById("promptHistory");

    if (historyList) {
        historyList.innerHTML = "";
    }

    updatePromptMeta({
        tokens_estimate: data.tokens_estimate,
        token_budget: data.token_budget,
        history_limit: 0,
        summary_token_limit: data.summary_token_limit,
        summary_was_trimmed: false
    });
}


// ==========================
// SEND MESSAGE
// ==========================
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

    clearPromptAfterSendKeepSummary();
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

    // Jeżeli prompt już był zbudowany/edytowany,
    // nie pobieramy go drugi raz z backendu.
    const existingMessages = buildMessagesFromPromptSections();

    if (existingMessages.length > 0) {
        return;
    }

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

// ==========================
// INIT
// ==========================
document.addEventListener(
    "DOMContentLoaded",
    () => {
        const input = document.getElementById("msg");
        const contextBox = document.getElementById("contextBox");
        const modelSelect = document.getElementById("modelSelect");

        loadModels();

        if (input) {
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

            input.addEventListener(
                "input",
                schedulePromptTokenEstimateUpdate
            );
        }

        if (contextBox) {
            contextBox.addEventListener(
                "input",
                schedulePromptTokenEstimateUpdate
            );
        }

        if (modelSelect) {
            modelSelect.addEventListener(
                "change",
                schedulePromptTokenEstimateUpdate
            );
        }

        schedulePromptTokenEstimateUpdate();
    }
);
