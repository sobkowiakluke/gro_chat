// ==========================
// PROMPT SECTIONS
// ==========================
let promptMemoryDirty = false;
let promptMemoryLoaded = false;

const DURABLE_PROMPT_SECTIONS = ["system", "summary", "facts", "decisions", "context"];

function getPromptMemoryOverrides() {
    const result = {};
    DURABLE_PROMPT_SECTIONS.forEach((name) => {
        const el = document.querySelector(`[data-memory-section="${name}"]`);
        result[name] = Boolean(el && el.checked);
    });
    return result;
}

function setPromptMemoryOverrides(overrides) {
    overrides = overrides || {};
    DURABLE_PROMPT_SECTIONS.forEach((name) => {
        const el = document.querySelector(`[data-memory-section="${name}"]`);
        if (el) el.checked = Boolean(overrides[name]);
    });
}

function markPromptEditedOnly() {
    if (typeof schedulePromptTokenEstimateUpdate === "function") {
        schedulePromptTokenEstimateUpdate();
    }
}


function markPromptMemoryDirty() {
    if (promptMemoryLoaded) {
        promptMemoryDirty = true;
    }

    if (typeof schedulePromptTokenEstimateUpdate === "function") {
        schedulePromptTokenEstimateUpdate();
    }
}


function resetPromptMemoryDirtyState() {
    promptMemoryDirty = false;
    promptMemoryLoaded = true;
}


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
    setPromptTextareaValue("promptFacts", "");
    setPromptTextareaValue("promptDecisions", "");
    setPromptTextareaValue("promptContext", "");
    setPromptTextareaValue("promptUser", "");

    const historyList = document.getElementById("promptHistory");

    if (historyList) {
        historyList.innerHTML = "";
    }

    setPromptMemoryOverrides({});

    const meta = document.getElementById("promptMeta");

    if (meta) {
        meta.innerText = "";
    }
}


function normalizeSummaryForPrompt(summary) {
    const value = (summary || "").trim();

    if (!value) {
        return "";
    }

    if (value.startsWith("STRESZCZENIE STARSZEJ CZĘŚCI ROZMOWY:")) {
        return value;
    }

    return "STRESZCZENIE STARSZEJ CZĘŚCI ROZMOWY:\n" + value;
}


function stripSummaryPrefix(summary) {
    return (summary || "")
        .replace(/^STRESZCZENIE STARSZEJ CZĘŚCI ROZMOWY:\n?/, "")
        .trim();
}


function stripFactsPrefix(facts) {
    return (facts || "")
        .replace(/^FAKTY USTALONE W ROZMOWIE:\n?/, "")
        .trim();
}


function stripDecisionsPrefix(decisions) {
    return (decisions || "")
        .replace(/^DECYZJE I ZAŁOŻENIA PROJEKTOWE:\n?/, "")
        .trim();
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

            <button type="button" onclick="this.closest('.prompt-history-item').remove(); markPromptEditedOnly();">
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

    roleSelect.addEventListener("change", markPromptEditedOnly);
    contentTextarea.addEventListener("input", markPromptEditedOnly);

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
        facts: [],
        decisions: [],
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
            sections.summary.push(stripSummaryPrefix(content));
            return;
        }

        if (
            role === "system" &&
            content.startsWith("FAKTY USTALONE W ROZMOWIE:")
        ) {
            sections.facts.push(stripFactsPrefix(content));
            return;
        }

        if (
            role === "system" &&
            content.startsWith("DECYZJE I ZAŁOŻENIA PROJEKTOWE:")
        ) {
            sections.decisions.push(stripDecisionsPrefix(content));
            return;
        }

        if (
            role === "system" &&
            (
                content.startsWith("KONTEKST:") ||
                content.startsWith("KONTEKST ROBOCZY / WORKSPACE:")
            )
        ) {
            sections.context.push(
                content
                    .replace(/^KONTEKST:\n?/, "")
                    .replace(/^KONTEKST ROBOCZY \/ WORKSPACE:\n?/, "")
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
    setPromptEditorKind("chat");

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
        "promptFacts",
        sections.facts.join("\n\n---\n\n")
    );

    setPromptTextareaValue(
        "promptDecisions",
        sections.decisions.join("\n\n---\n\n")
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

    attachPromptSectionDirtyListeners();
    resetPromptMemoryDirtyState();
}



function setPromptEditorKind(kind) {
    const normalizedKind = kind === "summary" ? "summary" : "chat";
    promptMode = normalizedKind;

    const label = document.getElementById("promptUserLabel");
    if (label) {
        label.innerHTML = normalizedKind === "summary"
            ? 'SUMMARY INSTRUCTION <span class="prompt-dynamic-note">tylko bieżące streszczanie</span>'
            : 'USER MESSAGE <span class="prompt-dynamic-note">tylko bieżące wysłanie</span>';
    }
}

function fillPromptSectionEditorsFromSections(sections, memoryOverrides = null) {
    clearPromptSectionEditors();

    sections = sections || {};
    setPromptEditorKind(sections.prompt_kind || "chat");

    setPromptTextareaValue(
        "promptSystem",
        sections.system || ""
    );

    setPromptTextareaValue(
        "promptSummary",
        stripSummaryPrefix(sections.summary || "")
    );

    setPromptTextareaValue(
        "promptFacts",
        stripFactsPrefix(sections.facts || "")
    );

    setPromptTextareaValue(
        "promptDecisions",
        stripDecisionsPrefix(sections.decisions || "")
    );

    setPromptTextareaValue(
        "promptContext",
        sections.context || ""
    );

    setPromptTextareaValue(
        "promptUser",
        sections.prompt_kind === "summary"
            ? (sections.summary_instruction || "")
            : (sections.user_message || "")
    );

    (sections.history || []).forEach((msg) => {
        addHistoryEditor(
            msg.role,
            msg.content
        );
    });

    setPromptMemoryOverrides(memoryOverrides || sections.prompt_memory_overrides || {});
    attachPromptSectionDirtyListeners();
    resetPromptMemoryDirtyState();
}


function buildPromptSectionsFromEditors() {
    const editorValue = getPromptTextareaValue("promptUser").trim();
    const isSummary = promptMode === "summary";

    return {
        prompt_kind: isSummary ? "summary" : "chat",
        system: getPromptTextareaValue("promptSystem").trim(),
        summary: getPromptTextareaValue("promptSummary").trim(),
        facts: getPromptTextareaValue("promptFacts").trim(),
        decisions: getPromptTextareaValue("promptDecisions").trim(),
        context: getPromptTextareaValue("promptContext").trim(),
        history: getHistoryMessagesFromEditors(),
        user_message: isSummary ? "" : editorValue,
        summary_instruction: isSummary ? editorValue : ""
    };
}


function buildMessagesFromPromptSections() {
    const messages = [];

    const system = getPromptTextareaValue("promptSystem").trim();
    const summary = getPromptTextareaValue("promptSummary").trim();
    const facts = getPromptTextareaValue("promptFacts").trim();
    const decisions = getPromptTextareaValue("promptDecisions").trim();
    const context = getPromptTextareaValue("promptContext").trim();
    const finalInstruction = getPromptTextareaValue("promptUser").trim();

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
            content: normalizeSummaryForPrompt(summary)
        });
    }

    if (facts) {
        messages.push({
            role: "system",
            content: "FAKTY USTALONE W ROZMOWIE:\n" + facts
        });
    }

    if (decisions) {
        messages.push({
            role: "system",
            content: "DECYZJE I ZAŁOŻENIA PROJEKTOWE:\n" + decisions
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

    if (finalInstruction) {
        messages.push({
            role: "user",
            content: finalInstruction
        });
    }

    return messages;
}


function getUserMessageFromPromptSections() {
    if (promptMode === "summary") {
        return "";
    }

    return getPromptTextareaValue("promptUser").trim();
}


function attachPromptSectionDirtyListeners() {
    const durableIds = [
        "promptSystem", "promptSummary", "promptFacts",
        "promptDecisions", "promptContext"
    ];
    durableIds.forEach((id) => {
        const el = document.getElementById(id);
        if (!el || el.dataset.promptDirtyListener === "1") return;
        el.addEventListener("input", markPromptMemoryDirty);
        el.dataset.promptDirtyListener = "1";
    });

    const user = document.getElementById("promptUser");
    if (user && user.dataset.promptDirtyListener !== "1") {
        user.addEventListener("input", markPromptEditedOnly);
        user.dataset.promptDirtyListener = "1";
    }

    document.querySelectorAll("[data-memory-section]").forEach((el) => {
        if (el.dataset.promptDirtyListener === "1") return;
        el.addEventListener("change", markPromptMemoryDirty);
        el.dataset.promptDirtyListener = "1";
    });
}


async function savePromptMemoryFromPopup() {
    const conversationId = getActiveConversationId();

    if (!conversationId) {
        alert("Najpierw utwórz albo wybierz chat.");
        return false;
    }

    const payload = getChatPayload();
    const promptSections = buildPromptSectionsFromEditors();

    let res;
    let data;

    try {
        res = await fetch(
            "/prompt-memory",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    conversation_id: conversationId,
                    model: payload.model,
                    prompt_sections: promptSections,
                    prompt_memory_overrides: getPromptMemoryOverrides()
                })
            }
        );

        data = await res.json();

    } catch (e) {
        alert(
            "Nie udało się zapisać pamięci promptu.\n\n" +
            String(e)
        );
        return false;
    }

    if (!res.ok) {
        alert(
            data.error ||
            "Nie udało się zapisać pamięci promptu."
        );
        return false;
    }

    if (data.prompt_sections) {
        fillPromptSectionEditorsFromSections(
            data.prompt_sections,
            data.prompt_memory_overrides
        );
    }

    updatePromptMeta(data);
    resetPromptMemoryDirtyState();

    return true;
}


async function resetPromptMemory() {
    const conversationId = getActiveConversationId();

    if (!conversationId) {
        alert("Najpierw utwórz albo wybierz chat.");
        return false;
    }

    const ok = confirm(
        "Usunąć zapisaną pamięć promptu dla tej rozmowy i wrócić do budowania z historii DB?"
    );

    if (!ok) {
        return false;
    }

    const res = await fetch(
        "/prompt-memory",
        {
            method: "DELETE",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                conversation_id: conversationId
            })
        }
    );

    const data = await res.json();

    if (!res.ok) {
        alert(data.error || "Nie udało się usunąć pamięci promptu.");
        return false;
    }

    promptMemoryDirty = false;
    promptMemoryLoaded = false;

    await toggleContext();
    await toggleContext();

    return true;
}


function updatePromptMeta(data) {
    const meta = document.getElementById("promptMeta");

    if (!meta) {
        return;
    }

    const parts = [];

    if (data.tokens_estimate !== undefined && data.token_budget !== undefined) {
        const budgetLabel = data.prompt_over_budget
            ? `PRZEKROCZONO: ${data.tokens_estimate} / ${data.token_budget}`
            : `tokeny: ${data.tokens_estimate} / ${data.token_budget}`;
        parts.push(budgetLabel);
    }

    if (data.prompt_excess_tokens) {
        parts.push(`nadmiar: ${data.prompt_excess_tokens}`);
    }

    if (data.prompt_source) {
        parts.push(`źródło: ${data.prompt_source}`);
    }

    if (data.summary_used !== undefined) {
        parts.push(data.summary_used ? "summary: tak" : "summary: nie");
    }

    if (data.history_messages_used !== undefined && data.history_messages_used !== null) {
        parts.push(
            `historia użyta: ${data.history_messages_used}`
        );
    } else if (data.history_limit !== undefined && data.history_limit !== null) {
        parts.push(
            `historia: ${data.history_limit}`
        );
    }

    if (data.history_messages_loaded !== undefined && data.history_messages_loaded !== null) {
        parts.push(
            `historia pobrana: ${data.history_messages_loaded}`
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

    if (data.summary_messages_remaining !== undefined && data.summary_messages_remaining !== null) {
        parts.push(`pozostało do summary: ${data.summary_messages_remaining}`);
    }

    meta.innerText = parts.join(" | ");
}


// ==========================
// BUILD SUMMARY PROMPT
// ==========================
async function compressHistoryToSummary() {
    const conversationId = getActiveConversationId();

    if (!conversationId) {
        alert("Najpierw utwórz albo wybierz chat.");
        return;
    }

    const model = getSelectedModel();

    let res;
    let data;

    try {
        res = await fetch("/summary-context", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                conversation_id: conversationId,
                model: model
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
            "Nie udało się zbudować payloadu summary."
        );

        return;
    }

    if (!Array.isArray(data.messages)) {
        showApiErrorPopup("Backend nie zwrócił messages dla summary.");
        return;
    }

    editedMessages = data.messages;
    setPromptEditorKind("summary");
    summaryUntilMessageId = data.summary_until_message_id;

    if (data.prompt_sections) {
        fillPromptSectionEditorsFromSections(data.prompt_sections, data.prompt_memory_overrides);
    } else {
        fillPromptSectionEditors(editedMessages);
    }

    updatePromptMeta(data);

    const batchInfo = data.summary_has_more
        ? ` Ta porcja obejmuje ${data.history_messages_used} z ${data.history_messages_loaded} wiadomości. Po zapisaniu pozostanie ${data.summary_messages_remaining}.`
        : ` Ta porcja obejmuje wszystkie ${data.history_messages_used} wiadomości oczekujące na summary.`;

    alert(
        "Payload summary jest widoczny w popupie." +
        batchInfo +
        " Sprawdź go i kliknij »Wyślij prompt«, jeżeli ma zostać wysłany do LLM."
    );
}


// ==========================
// SEND MESSAGE
// ==========================
async function sendEditedPrompt() {
    const conversationId = getActiveConversationId();

    if (!conversationId) {
        alert("Najpierw utwórz albo wybierz chat.");
        return;
    }

    const model = getSelectedModel();
    const promptSections = buildPromptSectionsFromEditors();
    const finalMessages = buildMessagesFromPromptSections();
    const userMessage = getUserMessageFromPromptSections();

    if (!userMessage && promptMode !== "summary") {
        alert("Brak wiadomości do wysłania.");
        return;
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
                body: JSON.stringify({
                    conversation_id: conversationId,
                    model: model,
                    message: userMessage,
                    prompt_sections: promptSections,
                    summary_mode: promptMode === "summary",
                    summary_until_message_id: summaryUntilMessageId,
                    persist_prompt_memory: promptMemoryDirty,
                    prompt_memory_overrides: getPromptMemoryOverrides()
                })
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
            "Błąd API Groq."
        );
        return;
    }

    if (data.summary_mode || data.summary_updated) {
        setPromptTextareaValue(
            "promptSummary",
            data.summary || data.reply || ""
        );

        setPromptEditorKind("chat");
        summaryUntilMessageId = null;

        updatePromptMeta(data);
        resetPromptMemoryDirtyState();

        if (typeof schedulePromptTokenEstimateUpdate === "function") {
            schedulePromptTokenEstimateUpdate();
        }

        const remaining = Number(data.summary_messages_remaining || 0);
        alert(
            remaining > 0
                ? `Summary porcji zostało zapisane. Pozostało ${remaining} wiadomości; użyj ponownie History → Summary.`
                : "Summary zostało zapisane i obejmuje całą oczekującą historię."
        );

        return;
    }

    promptMode = "chat";
    summaryUntilMessageId = null;
    editedMessages = null;
    promptMemoryDirty = false;

    const input = document.getElementById("msg");

    if (input) {
        input.value = "";
    }

    if (typeof closeContextModal === "function") {
        closeContextModal();
    }

    if (typeof loadConversationMessages === "function") {
        await loadConversationMessages(conversationId);
    }

    clearPromptSectionEditors();

    if (typeof schedulePromptTokenEstimateUpdate === "function") {
        schedulePromptTokenEstimateUpdate();
    }
}
