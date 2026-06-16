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
