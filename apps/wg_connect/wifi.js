(function () {
    "use strict";

    var API = "http://127.0.0.1:8554";
    var panel = new URLSearchParams(window.location.search).get("panel");
    if (panel !== "wifi" && panel !== "bluetooth") panel = "all";
    document.body.dataset.panel = panel;
    var token = "";
    var requestQueue = Promise.resolve();
    var capabilityRequest = null;
    var capabilities = null;
    var language = (function () {
        var stored = "";
        try {
            stored = localStorage.getItem("wg_lang") || "";
        } catch (error) {
            stored = "";
        }
        return (window.WG_LANG || {})[stored] || (window.WG_LANG || {})["zh-cn"] || {};
    })();

    function t(key, values) {
        var value = language[key] || key;
        Object.keys(values || {}).forEach(function (name) {
            value = value.replace("{" + name + "}", values[name]);
        });
        return value;
    }

    function fetchJson(url, options, timeout) {
        var sourceOptions = Object.assign({}, options || {});
        var headers = new Headers(sourceOptions.headers || {});
        if (url !== "/wg/ping" && token) headers.set("X-WG-Token", token);
        sourceOptions.headers = headers;
        var controller = new AbortController();
        var timer = setTimeout(function () { controller.abort(); }, timeout);
        sourceOptions.signal = controller.signal;
        return fetch(API + url, sourceOptions).then(function (response) {
            clearTimeout(timer);
            return response.json().then(function (body) {
                return { response: response, body: body };
            });
        }).catch(function (error) {
            clearTimeout(timer);
            throw error;
        });
    }

    function request(url, options, timeout) {
        var sourceOptions = Object.assign({}, options || {});
        function send(retried) {
            return fetchJson(url, sourceOptions, timeout).then(function (result) {
                var response = result.response;
                var body = result.body;
                token = response.headers.get("X-WG-Token") || token;
                if (!response.ok && body.error === "token_invalid" && !retried && url !== "/wg/ping") {
                    return fetchJson("/wg/ping", {}, 1500).then(function (ping) {
                        token = ping.response.headers.get("X-WG-Token") || token;
                        if (!ping.response.ok || ping.body.ok !== true) {
                            throw new Error(ping.body.message || t("serviceMissingDetail"));
                        }
                        return send(true);
                    });
                }
                if (!response.ok) {
                    var error = new Error(body.message || t("unknownError"));
                    error.code = body.error;
                    throw error;
                }
                return body;
            });
        }
        var task = requestQueue.then(function () {
            return send(false);
        });
        requestQueue = task.then(function () {}, function () {});
        return task;
    }

    function requestOptions(method, body) {
        var options = { method: method, headers: {} };
        if (body !== undefined) {
            options.headers["Content-Type"] = "application/json";
            options.body = JSON.stringify(body);
        }
        return options;
    }

    function probeCapabilities(force) {
        if (capabilityRequest) return capabilityRequest;
        if (!force && capabilities) return Promise.resolve(capabilities);
        capabilityRequest = request("/wg/ping", {}, 1500).then(function (data) {
            return { backend: data.ok === true, caps: Array.isArray(data.caps) ? data.caps : [] };
        }).catch(function () {
            return { backend: false, caps: [] };
        }).then(function (result) {
            capabilities = result;
            capabilityRequest = null;
            return result;
        });
        return capabilityRequest;
    }

    window.WG_CONNECT_API = {
        request: request,
        requestOptions: requestOptions,
        probe: probeCapabilities
    };

    document.querySelectorAll("[data-wg-i18n]").forEach(function (element) {
        element.textContent = t(element.getAttribute("data-wg-i18n"));
    });
    document.querySelectorAll("[data-wg-i18n-placeholder]").forEach(function (element) {
        element.placeholder = t(element.getAttribute("data-wg-i18n-placeholder"));
    });
    var pageTitle = panel === "wifi" ? t("wifiPageTitle") : panel === "bluetooth" ? t("bluetoothPageTitle") : t("title");
    document.title = pageTitle;
    document.querySelector(".topbar h1").textContent = pageTitle;
    if (panel === "bluetooth") return;

    var service = document.getElementById("service");
    var serviceTitle = document.getElementById("serviceTitle");
    var serviceDetail = document.getElementById("serviceDetail");
    var serverRefreshButton = document.getElementById("serverRefreshButton");
    var downloadService = document.getElementById("downloadService");
    var refreshButton = document.getElementById("refreshButton");
    var wifiPowerStatus = document.getElementById("wifiPowerStatus");
    var wifiToggleButton = document.getElementById("wifiToggleButton");
    var networkState = document.getElementById("networkState");
    var networkList = document.getElementById("networkList");
    var connectForm = document.getElementById("connectForm");
    var selectedName = document.getElementById("selectedName");
    var passwordInput = document.getElementById("password");
    var connectButton = document.getElementById("connectButton");
    var resultMessage = document.getElementById("resultMessage");
    var networks = [];
    var selectedNetwork = null;
    var busy = false;
    var wifiAvailable = false;
    var adapterAvailable = false;
    var wifiEnabled = false;
    var wifiStatusKnown = false;

    function setService(state, title, detail) {
        service.dataset.state = state;
        serviceTitle.textContent = title;
        serviceDetail.textContent = detail || "";
        serverRefreshButton.disabled = state === "checking" || busy;
        if (downloadService) downloadService.hidden = true;
    }

    function setNotice(message, isError) {
        resultMessage.textContent = message || "";
        resultMessage.hidden = !message;
        resultMessage.classList.toggle("error", !!isError);
    }

    function renderWifiControls() {
        var statusKey = "wifiStateUnknown";
        if (wifiAvailable && wifiStatusKnown) {
            statusKey = adapterAvailable ? (wifiEnabled ? "wifiOn" : "wifiOff") : "wifiNoAdapter";
        }
        wifiPowerStatus.textContent = t(statusKey);
        wifiToggleButton.textContent = t(wifiEnabled ? "wifiTurnOff" : "wifiTurnOn");
        wifiToggleButton.disabled = busy || !wifiAvailable || !adapterAvailable;
        refreshButton.disabled = busy || !wifiAvailable || !adapterAvailable || !wifiEnabled;
    }

    function renderNetworks() {
        networkList.textContent = "";
        networks.forEach(function (network) {
            var item = document.createElement("div");
            item.className = "network-item";
            var button = document.createElement("button");
            button.type = "button";
            button.className = "network";
            button.setAttribute("aria-pressed", selectedNetwork && selectedNetwork.ssid === network.ssid ? "true" : "false");
            button.disabled = busy || !network.connectable || network.connected;

            var name = document.createElement("span");
            name.className = "network-name";
            name.textContent = network.ssid;

            if (network.connected) {
                var connected = document.createElement("span");
                connected.className = "badge";
                connected.textContent = t("connected");
                name.appendChild(connected);
            }

            var meta = document.createElement("span");
            meta.className = "network-meta";
            meta.textContent = network.connectable
                ? (network.open ? t("openNetwork") : t("secured")) + " · " + network.security
                : t("unsupported") + " · " + network.security;
            name.appendChild(meta);

            var signal = document.createElement("span");
            signal.className = "signal";
            signal.setAttribute("aria-hidden", "true");
            var level = network.signal >= 80 ? 4 : network.signal >= 60 ? 3 : network.signal >= 35 ? 2 : 1;
            signal.dataset.level = String(level);
            for (var index = 0; index < 4; index++) signal.appendChild(document.createElement("i"));
            button.setAttribute("aria-label", network.ssid + ", " + t("signalLabel", { level: level }));
            button.appendChild(signal);
            button.appendChild(name);
            button.addEventListener("click", function () { selectNetwork(network); });
            item.appendChild(button);
            if (network.connected) {
                var disconnect = document.createElement("button");
                disconnect.type = "button";
                disconnect.className = "network-disconnect";
                disconnect.textContent = t("disconnect");
                disconnect.disabled = busy || !wifiAvailable || !wifiEnabled;
                disconnect.addEventListener("click", function () { disconnectNetwork(network.ssid); });
                item.appendChild(disconnect);
            }
            networkList.appendChild(item);
        });
    }

    function selectNetwork(network) {
        if (busy || !network.connectable) return;
        selectedNetwork = network;
        selectedName.textContent = network.ssid;
        passwordInput.value = "";
        passwordInput.required = !network.open;
        passwordInput.hidden = network.open;
        connectForm.hidden = false;
        setNotice(network.open ? t("openWarning") : "", false);
        renderNetworks();
        if (!network.open) passwordInput.focus();
    }

    function hideForm() {
        connectForm.hidden = true;
        selectedNetwork = null;
        renderNetworks();
    }

    function showScanState(message, loading, isError) {
        networkState.hidden = false;
        networkState.classList.toggle("error", !!isError);
        networkState.innerHTML = loading ? '<span class="spinner" aria-hidden="true"></span>' : "";
        if (!loading) networkState.textContent = message;
        if (loading) networkState.appendChild(document.createTextNode(message));
    }

    function scan() {
        if (busy || !token || !wifiEnabled) return Promise.resolve();
        busy = true;
        serverRefreshButton.disabled = true;
        connectButton.disabled = true;
        renderWifiControls();
        showScanState(t("scanning"), true, false);
        networkList.textContent = "";
        setNotice("", false);
        return request("/wg/wifi/scan", requestOptions("GET"), 16000).then(function (data) {
            networks = Array.isArray(data.networks) ? data.networks : [];
            var connectedSsids = Array.isArray(data.connected_ssids)
                ? data.connected_ssids
                : data.connected_ssid ? [data.connected_ssid] : [];
            networks.forEach(function (network) {
                network.connected = connectedSsids.indexOf(network.ssid) !== -1;
            });
            renderNetworks();
            if (networks.length) {
                networkState.hidden = true;
            } else {
                showScanState(t("scanEmpty"), false, false);
            }
            setNotice("", false);
        }).catch(function (error) {
            showScanState(t("scanFailed"), false, true);
            setNotice(error.code ? t("serviceError", { message: error.message }) : t("unknownError"), true);
        }).then(function () {
            busy = false;
            serverRefreshButton.disabled = false;
            connectButton.disabled = false;
            renderWifiControls();
            renderNetworks();
        });
    }

    function setUnavailable(message) {
        wifiAvailable = false;
        adapterAvailable = false;
        wifiStatusKnown = false;
        setService("error", t("serviceMissing"), message || t("serviceMissingDetail"));
        if (downloadService) downloadService.hidden = false;
        serverRefreshButton.disabled = false;
        renderWifiControls();
        showScanState(t("serviceNeeded"), false, false);
    }

    function loadWifiStatus() {
        busy = true;
        wifiStatusKnown = false;
        serverRefreshButton.disabled = true;
        renderWifiControls();
        wifiPowerStatus.textContent = t("wifiStateChecking");
        return request("/wg/wifi/status", requestOptions("GET"), 5000).then(function (status) {
            adapterAvailable = status.available === true;
            wifiEnabled = status.enabled === true;
            wifiStatusKnown = true;
            busy = false;
            renderWifiControls();
            if (!adapterAvailable) {
                networks = [];
                renderNetworks();
                showScanState(t("wifiNoAdapter"), false, true);
                return;
            }
            if (!wifiEnabled) {
                hideForm();
                networks = [];
                renderNetworks();
                showScanState(t("wifiOffList"), false, false);
                return;
            }
            return scan();
        }).catch(function (error) {
            busy = false;
            adapterAvailable = false;
            wifiStatusKnown = false;
            renderWifiControls();
            showScanState(t("scanFailed"), false, true);
            setNotice(error.code ? t("serviceError", { message: error.message }) : t("unknownError"), true);
        }).then(function () {
            serverRefreshButton.disabled = false;
        });
    }

    function recheckServer() {
        if (busy) return Promise.resolve();
        busy = true;
        wifiAvailable = false;
        adapterAvailable = false;
        wifiStatusKnown = false;
        token = "";
        setService("checking", t("serviceChecking"), "");
        serverRefreshButton.disabled = true;
        renderWifiControls();
        setNotice("", false);
        return probeCapabilities(true).then(function (data) {
            if (!data.backend) {
                setUnavailable(window.location.protocol === "file:" ? t("fileWarning") : t("serviceMissingDetail"));
                return;
            }
            if (data.caps.indexOf("wifi") === -1) {
                busy = false;
                setService("error", t("serviceMissing"), t("serviceNoWifi"));
                renderWifiControls();
                showScanState(t("serviceNeeded"), false, false);
                return;
            }
            wifiAvailable = true;
            setService("ready", t("serviceReady"), "");
            busy = false;
            return loadWifiStatus();
        }).catch(function () {
            busy = false;
            setUnavailable(window.location.protocol === "file:" ? t("fileWarning") : t("serviceMissingDetail"));
        });
    }

    function bootstrap() {
        return probeCapabilities(false).then(function (data) {
            if (!data.backend) {
                setUnavailable(window.location.protocol === "file:" ? t("fileWarning") : t("serviceMissingDetail"));
                return;
            }
            if (data.caps.indexOf("wifi") === -1) {
                wifiAvailable = false;
                wifiStatusKnown = false;
                setService("error", t("serviceMissing"), t("serviceNoWifi"));
                renderWifiControls();
                showScanState(t("serviceNeeded"), false, false);
                return;
            }
            wifiAvailable = true;
            setService("ready", t("serviceReady"), "");
            return loadWifiStatus();
        }).catch(function () {
            setUnavailable(window.location.protocol === "file:" ? t("fileWarning") : t("serviceMissingDetail"));
        });
    }

    refreshButton.addEventListener("click", scan);
    serverRefreshButton.addEventListener("click", recheckServer);
    function disconnectNetwork(ssid) {
        if (busy) return Promise.resolve();
        busy = true;
        renderWifiControls();
        wifiPowerStatus.textContent = t("wifiDisconnecting");
        serverRefreshButton.disabled = true;
        setNotice("", false);
        return request("/wg/wifi/disconnect", requestOptions("POST", { ssid: ssid }), 12000).then(function (result) {
            busy = false;
            renderWifiControls();
            return loadWifiStatus().then(function () {
                setNotice(t("disconnectSuccess", { ssid: result.ssid || ssid }), false);
            });
        }).catch(function (error) {
            busy = false;
            renderWifiControls();
            var message = error.message || t("unknownError");
            return loadWifiStatus().then(function () {
                setNotice(message, true);
            });
        }).then(function () {
            serverRefreshButton.disabled = false;
        });
    }

    wifiToggleButton.addEventListener("click", function () {
        if (busy || !adapterAvailable) return;
        var enabled = !wifiEnabled;
        if (!enabled && !window.confirm(t("wifiTurnOffConfirm"))) return;
        busy = true;
        renderWifiControls();
        wifiPowerStatus.textContent = t(enabled ? "wifiTurningOn" : "wifiTurningOff");
        serverRefreshButton.disabled = true;
        setNotice("", false);
        request("/wg/wifi/toggle", requestOptions("POST", { enabled: enabled }), 12000).then(function (status) {
            adapterAvailable = status.available === true;
            wifiEnabled = status.enabled === true;
            wifiStatusKnown = true;
            busy = false;
            renderWifiControls();
            if (wifiEnabled) return scan();
            hideForm();
            networks = [];
            renderNetworks();
            showScanState(t("wifiOffList"), false, false);
        }).catch(function (error) {
            busy = false;
            renderWifiControls();
            var message = error.message || t("unknownError");
            return loadWifiStatus().then(function () {
                setNotice(message, true);
            });
        }).then(function () {
            serverRefreshButton.disabled = false;
            connectButton.disabled = false;
        });
    });
    document.getElementById("cancelButton").addEventListener("click", hideForm);
    connectForm.addEventListener("submit", function (event) {
        event.preventDefault();
        if (!selectedNetwork || busy) return;
        if (!selectedNetwork.open && !passwordInput.value) {
            setNotice(t("emptyPassword"), true);
            passwordInput.focus();
            return;
        }
        busy = true;
        connectButton.disabled = true;
        refreshButton.disabled = true;
        serverRefreshButton.disabled = true;
        connectButton.textContent = t("connecting");
        setNotice(t("connecting"), false);
        request("/wg/wifi/connect", requestOptions("POST", {
            ssid: selectedNetwork.ssid,
            password: passwordInput.value
        }), 60000).then(function (result) {
            passwordInput.value = "";
            hideForm();
            busy = false;
            return scan().then(function () {
                setNotice(t("connectedSuccess", { ssid: result.ssid }), false);
            });
        }).catch(function (error) {
            passwordInput.value = "";
            setNotice(error.code ? t("serviceError", { message: error.message }) : t("connectionFailed"), true);
        }).then(function () {
            busy = false;
            connectButton.disabled = false;
            serverRefreshButton.disabled = false;
            connectButton.textContent = t("connect");
            renderWifiControls();
            renderNetworks();
        });
    });

    bootstrap();
})();
