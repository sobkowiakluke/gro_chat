function refreshTree() {

    const container = document.getElementById("gitTree");
    container.innerHTML = "";

    renderTree(window.repoData, container);
}

function renderTree(node, container, basePath = "") {

    const ul = document.createElement("ul");

    /* =========================
       FOLDERY
    ========================= */

    for (const key in node) {

        if (
            key === "_files" ||
            key === "_file_functions" ||
            key === "_file_classes"
        ) {
            continue;
        }

        const folderPath = basePath + key;

        const li = document.createElement("li");

        const header = document.createElement("div");
        header.className = "folder-header";

        const isCollapsed = window.collapsedFolders.has(folderPath);

        header.textContent = (isCollapsed ? "▶ " : "▼ ") + key;

        const childContainer = document.createElement("div");
        childContainer.style.marginLeft = "15px";
        childContainer.style.display = isCollapsed ? "none" : "block";

        header.onclick = (e) => {

            e.stopPropagation();

            if (window.collapsedFolders.has(folderPath)) {
                window.collapsedFolders.delete(folderPath);
            } else {
                window.collapsedFolders.add(folderPath);
            }

            refreshTree();
        };

        renderTree(
            node[key],
            childContainer,
            folderPath + "/"
        );

        li.appendChild(header);
        li.appendChild(childContainer);
        ul.appendChild(li);
    }

    /* =========================
       PLIKI
    ========================= */

    if (node._files) {

        node._files.forEach(file => {

            const li = document.createElement("li");
            li.className = "git-file";
            li.textContent = "📄 " + file;

            li.onclick = (e) => {
                e.stopPropagation();
                window.loadFile(basePath + file);
            };

            /* =========================
               FUNKCJE
            ========================= */

            if (
                node._file_functions &&
                node._file_functions[file]
            ) {

                const fnUl = document.createElement("ul");
                fnUl.style.marginLeft = "15px";

                node._file_functions[file].forEach(fn => {

                    const fnLi = document.createElement("li");
                    fnLi.className = "git-func";
                    fnLi.textContent = "ƒ " + fn.name;

                    fnLi.onclick = (e) => {
                        e.stopPropagation();
                        window.loadFunction(fn.file, fn.name);
                    };

                    fnUl.appendChild(fnLi);
                });

                li.appendChild(fnUl);
            }

            ul.appendChild(li);
        });
    }

    container.appendChild(ul);
}

async function loadGitTree() {

    const container = document.getElementById("gitTree");

    try {

        const res = await fetch("/git-tree");
        window.repoData = await res.json();

        container.innerHTML = "";

        renderTree(window.repoData, container);

    } catch (err) {

        console.error("Git tree error:", err);
    }
}

/* =========================
   EXPORT GLOBALNY
========================= */

window.loadGitTree = loadGitTree;
window.refreshTree = refreshTree;
window.renderTree = renderTree;
document.addEventListener("DOMContentLoaded", () => {
    loadGitTree();
});
