(function () {
    "use strict";

    const pending = new Map();
    const relayedRequests = new Map();
    const dialogQueue = [];
    let activeDialog = null;
    let sequence = 0;
    const requestNamespace = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    let toastStack = null;
    let stylesheetAdded = false;

    function ensureStylesheet() {
        if (stylesheetAdded || !document.head) return;
        if (document.querySelector("link[data-wgui-styles]")) {
            stylesheetAdded = true;
            return;
        }
        const script = document.currentScript || document.querySelector('script[src$="wgui.js"]');
        if (!script || !script.src) {
            throw new Error("WGUI stylesheet path is unavailable.");
        }
        const link = document.createElement("link");
        link.rel = "stylesheet";
        link.href = new URL("wgui.css", script.src).href;
        document.head.appendChild(link);
        stylesheetAdded = true;
    }

    function isHost() {
        return window === window.parent;
    }

    function expectedMessageOrigin() {
        return window.location.protocol === "file:" ? "null" : window.location.origin;
    }

    function createRequestId() {
        sequence += 1;
        return `${requestNamespace}-${sequence}`;
    }

    function request(kind, options) {
        const settings = options || {};
        const id = createRequestId();
        const data = {
            action: "dialog",
            kind,
            id,
            title: typeof settings.title === "string" ? settings.title : "",
            message: typeof settings.message === "string" ? settings.message : String(settings.message || ""),
            type: settings.type,
            closeOnBackdrop: settings.closeOnBackdrop === true
        };

        if (isHost()) {
            return enqueueDialog(data);
        }

        return new Promise(resolve => {
            pending.set(id, { resolve, kind });
            window.parent.postMessage(data, "*");
        });
    }

    function alertDialog(options) {
        return request("alert", options);
    }

    function confirmDialog(options) {
        return request("confirm", options);
    }

    function toast(message, duration) {
        const settings = {
            message: typeof message === "string" ? message : String(message || ""),
            duration: Number.isFinite(Number(duration)) ? Number(duration) : 2600
        };
        if (isHost()) {
            showToast(settings.message, settings.duration);
            return;
        }
        window.parent.postMessage({ action: "dialog", kind: "toast", ...settings }, "*");
    }

    function enqueueDialog(data, source) {
        return new Promise(resolve => {
            dialogQueue.push({ data, source: source || null, resolve });
            showNextDialog();
        });
    }

    function showNextDialog() {
        if (activeDialog || dialogQueue.length === 0) return;
        ensureStylesheet();

        const item = dialogQueue.shift();
        const data = item.data;
        const kind = data.kind === "confirm" ? "confirm" : "alert";
        const type = ["success", "warning", "error"].includes(data.type) ? data.type : "info";
        const previousFocus = document.activeElement;
        const overlay = document.createElement("div");
        overlay.className = "wgui-overlay";
        overlay.setAttribute("data-wgui-overlay", "");

        const dialog = document.createElement("section");
        dialog.className = "wgui-dialog";
        dialog.dataset.type = type;
        dialog.dataset.theme = localStorage.getItem("WG_color") === "b" ? "b" : "w";
        dialog.setAttribute("role", "alertdialog");
        dialog.setAttribute("aria-modal", "true");
        dialog.setAttribute("aria-labelledby", "wgui-dialog-title");
        dialog.setAttribute("aria-describedby", "wgui-dialog-message");

        const main = document.createElement("div");
        main.className = "wgui-dialog-main";
        const icon = document.createElement("div");
        icon.className = "wgui-dialog-icon";
        icon.setAttribute("aria-hidden", "true");
        icon.textContent = type === "success" ? "✓" : type === "warning" ? "!" : type === "error" ? "×" : "i";

        const copy = document.createElement("div");
        copy.className = "wgui-dialog-copy";
        const title = document.createElement("h2");
        title.className = "wgui-dialog-title";
        title.id = "wgui-dialog-title";
        title.textContent = data.title || (kind === "confirm" ? "请确认" : "提示");
        const message = document.createElement("p");
        message.className = "wgui-dialog-message";
        message.id = "wgui-dialog-message";
        message.textContent = data.message;
        copy.append(title, message);
        main.append(icon, copy);

        const footer = document.createElement("div");
        footer.className = "wgui-dialog-footer";
        const cancel = document.createElement("button");
        cancel.className = "wgui-button";
        cancel.type = "button";
        cancel.textContent = kind === "confirm" ? "取消" : "关闭";
        const primary = document.createElement("button");
        primary.className = "wgui-button wgui-button-primary";
        primary.type = "button";
        primary.textContent = "确定";
        if (kind === "confirm") footer.appendChild(cancel);
        footer.appendChild(primary);
        dialog.append(main, footer);
        overlay.appendChild(dialog);

        activeDialog = {
            item,
            overlay,
            dialog,
            previousFocus,
            kind,
            closed: false,
            closeOnBackdrop: data.closeOnBackdrop === true
        };

        primary.addEventListener("click", () => closeDialog(true));
        if (kind === "confirm") {
            cancel.addEventListener("click", () => closeDialog(false));
        }
        overlay.addEventListener("click", event => {
            if (event.target === overlay && activeDialog.closeOnBackdrop) {
                closeDialog(kind === "confirm" ? false : undefined);
            }
        });
        document.addEventListener("keydown", handleDialogKeydown, true);
        document.body.appendChild(overlay);
        primary.focus();
    }

    function handleDialogKeydown(event) {
        if (!activeDialog) return;
        if (event.key === "Escape") {
            event.preventDefault();
            closeDialog(activeDialog.kind === "confirm" ? false : undefined);
        } else if (event.key === "Enter") {
            event.preventDefault();
            closeDialog(true);
        } else if (event.key === "Tab") {
            const buttons = Array.from(activeDialog.dialog.querySelectorAll("button"));
            const first = buttons[0];
            const last = buttons[buttons.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        }
    }

    function closeDialog(result) {
        if (!activeDialog || activeDialog.closed) return;
        const current = activeDialog;
        current.closed = true;
        activeDialog = null;
        document.removeEventListener("keydown", handleDialogKeydown, true);
        current.overlay.classList.add("wgui-closing");

        window.setTimeout(() => {
            current.overlay.remove();
            if (current.previousFocus && current.previousFocus.isConnected
                && typeof current.previousFocus.focus === "function") {
                current.previousFocus.focus();
            }
            current.item.resolve(current.kind === "confirm" ? result === true : undefined);
            if (current.item.source && current.item.data.id) {
                current.item.source.postMessage({
                    action: "dialog-result",
                    id: current.item.data.id,
                    result: current.kind === "confirm" ? result === true : undefined
                }, "*");
            }
            showNextDialog();
        }, 140);
    }

    function showToast(message, duration) {
        ensureStylesheet();
        if (!toastStack) {
            toastStack = document.createElement("div");
            toastStack.className = "wgui-toast-stack";
            toastStack.setAttribute("role", "status");
            toastStack.setAttribute("aria-live", "polite");
            document.body.appendChild(toastStack);
        }
        const item = document.createElement("div");
        item.className = "wgui-toast";
        item.textContent = message;
        toastStack.appendChild(item);
        const delay = Math.min(10000, Math.max(1000, duration));
        window.setTimeout(() => {
            item.classList.add("wgui-toast-out");
            window.setTimeout(() => item.remove(), 160);
        }, delay);
    }

    function handleRequest(event) {
        const data = event.data;
        if (!data || data.action !== "dialog") return;
        if (data.kind === "toast") {
            showToast(
                typeof data.message === "string" ? data.message : "",
                Number.isFinite(Number(data.duration)) ? Number(data.duration) : 2600
            );
            return;
        }
        if ((data.kind !== "alert" && data.kind !== "confirm") || typeof data.id !== "string") return;
        enqueueDialog({
            ...data,
            title: typeof data.title === "string" ? data.title.slice(0, 160) : "",
            message: typeof data.message === "string" ? data.message.slice(0, 4000) : ""
        }, event.source);
    }

    function isDirectChild(source) {
        return Array.from(document.querySelectorAll("iframe"))
            .some(frame => frame.contentWindow === source);
    }

    window.addEventListener("message", event => {
        const data = event.data;
        if (isHost() || event.origin !== expectedMessageOrigin() || !data) return;

        if (event.source === window.parent && data.action === "dialog-result"
            && typeof data.id === "string") {
            if (pending.has(data.id)) {
                const request = pending.get(data.id);
                pending.delete(data.id);
                request.resolve(request.kind === "confirm" ? data.result === true : undefined);
            } else if (relayedRequests.has(data.id)) {
                const child = relayedRequests.get(data.id);
                relayedRequests.delete(data.id);
                child.postMessage(data, "*");
            }
            return;
        }

        if (!isDirectChild(event.source) || data.action !== "dialog") return;
        if (data.kind === "toast") {
            window.parent.postMessage(data, "*");
            return;
        }
        if ((data.kind !== "alert" && data.kind !== "confirm") || typeof data.id !== "string") return;
        relayedRequests.set(data.id, event.source);
        window.parent.postMessage(data, "*");
    });

    window.WGUI = {
        alert: alertDialog,
        confirm: confirmDialog,
        toast,
        handleRequest,
        refreshTheme() {
            if (activeDialog) {
                activeDialog.dialog.dataset.theme = localStorage.getItem("WG_color") === "b" ? "b" : "w";
            }
        }
    };
})();
