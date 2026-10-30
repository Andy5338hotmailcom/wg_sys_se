(function () {
    const DEFAULT_WALLPAPER = "./wallpaper/wildgoose/bg.jpg";
    const wallpaperCategories = [
        {
            name: "wildgoose",
            images: [
                { name: "bg.jpg", path: "./wallpaper/wildgoose/bg.jpg" }
            ]
        },
        {
            name: "wip12",
            images: [
                { name: "WP12-DM-blue.png", path: "./wallpaper/wip12/WP12-DM-blue.png" },
                { name: "WP12-DM-green.png", path: "./wallpaper/wip12/WP12-DM-green.png" },
                { name: "WP12-DM-orange.png", path: "./wallpaper/wip12/WP12-DM-orange.png" },
                { name: "WP12-DM-purple.png", path: "./wallpaper/wip12/WP12-DM-purple.png" },
                { name: "WP12-DM.png", path: "./wallpaper/wip12/WP12-DM.png" },
                { name: "WP12-LM-blue.png", path: "./wallpaper/wip12/WP12-LM-blue.png" },
                { name: "WP12-LM-green.png", path: "./wallpaper/wip12/WP12-LM-green.png" },
                { name: "WP12-LM-orange.png", path: "./wallpaper/wip12/WP12-LM-orange.png" },
                { name: "WP12-LM-purple.png", path: "./wallpaper/wip12/WP12-LM-purple.png" },
                { name: "WP12-LM.png", path: "./wallpaper/wip12/WP12-LM.png" }
            ]
        }
    ];

    function currentWallpaper() {
        return localStorage.getItem("WG_desktop_wallpaper") || DEFAULT_WALLPAPER;
    }

    function updateSelection() {
        const selected = currentWallpaper();
        document.querySelectorAll(".wallpaper-card").forEach(card => {
            const isSelected = card.dataset.wallpaper === selected;
            card.classList.toggle("selected", isSelected);
            card.setAttribute("aria-pressed", String(isSelected));
        });
    }

    function applyWallpaper(path) {
        const wallpaper = path.trim();
        if (!wallpaper) {
            alert("请输入图片路径或 URL。");
            return;
        }
        localStorage.setItem("WG_desktop_wallpaper", wallpaper);
        parent.postMessage({ action: "desktop-wallpaper-change", wallpaper }, "*");
        wallpaperInput.value = wallpaper;
        updateSelection();
    }

    const categoriesContainer = document.getElementById("wallpaper-categories");
    wallpaperCategories.forEach(category => {
        const section = document.createElement("section");
        section.className = "wallpaper-category";

        const heading = document.createElement("h4");
        heading.textContent = category.name;
        section.appendChild(heading);

        const grid = document.createElement("div");
        grid.className = "wallpaper-grid";
        category.images.forEach(image => {
            const card = document.createElement("button");
            card.type = "button";
            card.className = "wallpaper-card";
            card.dataset.wallpaper = image.path;
            card.setAttribute("aria-label", `应用壁纸 ${image.name}`);
            card.addEventListener("click", () => applyWallpaper(image.path));

            const preview = document.createElement("img");
            preview.src = `../../wallpaper/${category.name}/${image.name}`;
            preview.alt = image.name;
            preview.loading = "lazy";

            const label = document.createElement("span");
            label.textContent = image.name;

            card.append(preview, label);
            grid.appendChild(card);
        });
        section.appendChild(grid);
        categoriesContainer.appendChild(section);
    });

    const wallpaperInput = document.getElementById("wallpaper-url");
    wallpaperInput.value = currentWallpaper();
    document.getElementById("apply-wallpaper-url").addEventListener("click", () => {
        applyWallpaper(wallpaperInput.value);
    });
    window.addEventListener("storage", event => {
        if (event.key !== "WG_desktop_wallpaper") return;
        wallpaperInput.value = event.newValue || DEFAULT_WALLPAPER;
        updateSelection();
    });
    updateSelection();
})();
