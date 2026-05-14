async function loadFile(path) {

    const res = await fetch(`/file?path=${encodeURIComponent(path)}`);
    const data = await res.json();

    document.getElementById("contextBox").value =
`FILE: ${data.path}

${data.content}`;
}

async function loadFunction(path, name) {

    const res = await fetch(
        `/function?path=${encodeURIComponent(path)}&name=${encodeURIComponent(name)}`
    );

    const data = await res.json();

    document.getElementById("contextBox").value =
`FUNCTION: ${data.name}

FILE: ${data.path}

${data.content}`;
}
window.loadFile = loadFile;
window.loadFunction = loadFunction;
async function loadModels() {

    const select = document.getElementById("modelSelect");

    if (!select) {
        console.error("modelSelect not found");
        return;
    }

    try {

        const res = await fetch("/models");

        if (!res.ok) {
            console.error("models endpoint error:", res.status);
            return;
        }

        const models = await res.json();

        console.log("MODELS:", models);

        select.innerHTML = "";

        models.forEach((m, index) => {

            const opt = document.createElement("option");
            opt.value = m;
            opt.textContent = m;

            if (index === 0) {
                opt.selected = true;
            }

            select.appendChild(opt);
        });

    } catch (err) {
        console.error("loadModels error:", err);
    }
}

window.loadModels = loadModels;
