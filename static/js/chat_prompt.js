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
