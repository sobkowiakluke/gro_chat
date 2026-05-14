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
