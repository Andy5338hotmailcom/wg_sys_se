(function () {
    "use strict";

    var panel = document.body.dataset.panel;
    if (panel === "wifi") return;

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

    var api = window.WG_CONNECT_API;
    var status = document.getElementById("bluetoothStatus");
    var detail = document.getElementById("bluetoothDetail");
    var refreshButton = document.getElementById("refreshBluetoothButton");
    var scanButton = document.getElementById("scanBluetoothButton");
    var bleButton = document.getElementById("connectBleButton");
    var pairedSection = document.getElementById("pairedSection");
    var pairedState = document.getElementById("pairedState");
    var pairedList = document.getElementById("pairedDevices");
    var nearbySection = document.getElementById("nearbySection");
    var nearbyState = document.getElementById("nearbyState");
    var nearbyList = document.getElementById("nearbyDevices");
    var notice = document.getElementById("bluetoothNotice");
    var refreshServerButton = document.getElementById("serverRefreshButton");
    var pairedDevices = [];
    var nearbyDevices = [];
    var serviceAvailable = false;
    var adapterAvailable = false;
    var busy = false;
    var bleDevice = null;

    function setNotice(message, isError) {
        notice.textContent = message || "";
        notice.hidden = !message;
        notice.classList.toggle("error", !!isError);
    }

    function updateControls() {
        refreshButton.disabled = busy;
        scanButton.disabled = busy || !serviceAvailable || !adapterAvailable;
        bleButton.hidden = !canUseWebBluetooth();
        bleButton.disabled = busy;
        if (!pairedSection.hidden) renderDevices(pairedList, pairedDevices, false);
        if (!nearbySection.hidden) renderDevices(nearbyList, nearbyDevices, true);
    }

    function canUseWebBluetooth() {
        return window.isSecureContext && navigator.bluetooth &&
            typeof navigator.bluetooth.requestDevice === "function";
    }

    function setState(message, isError) {
        status.textContent = message;
        status.classList.toggle("error", !!isError);
    }

    function renderDevices(list, devices, nearby) {
        list.textContent = "";
        devices.forEach(function (device) {
            var item = document.createElement("div");
            item.className = "device-item";
            var identity = document.createElement("div");
            identity.className = "device-identity";
            var name = document.createElement("span");
            name.className = "device-name";
            name.textContent = device.name || device.address;
            var address = document.createElement("span");
            address.className = "device-address";
            address.textContent = device.address;
            identity.appendChild(name);
            identity.appendChild(address);
            item.appendChild(identity);

            var action = document.createElement("button");
            action.type = "button";
            action.className = "action device-action";
            if (nearby && device.paired) {
                action.textContent = t("bluetoothPairedBadge");
                action.disabled = true;
            } else if (nearby) {
                action.textContent = t("bluetoothPair");
                action.classList.add("primary");
                action.disabled = busy;
                action.addEventListener("click", function () { pairDevice(device); });
            } else {
                action.textContent = t("bluetoothUnpair");
                action.disabled = busy;
                action.addEventListener("click", function () { unpairDevice(device); });
            }
            item.appendChild(action);
            list.appendChild(item);
        });
    }

    function probeService(force) {
        return api.probe(force);
    }

    function loadBluetooth(forceProbe) {
        busy = true;
        updateControls();
        setNotice("", false);
        setState(t("bluetoothChecking"), false);
        detail.textContent = t("bluetoothLoading");
        return probeService(!!forceProbe).then(function (result) {
            if (!result.backend || result.caps.indexOf("bluetooth") === -1) {
                serviceAvailable = false;
                adapterAvailable = false;
                pairedSection.hidden = true;
                nearbySection.hidden = true;
                setState(t("bluetoothUnavailable"), true);
                detail.textContent = canUseWebBluetooth()
                    ? t("bluetoothWebFallback")
                    : window.location.protocol === "file:"
                        ? t("bluetoothFileUnavailable")
                        : t("bluetoothServiceRequired");
                return;
            }
            serviceAvailable = true;
            return api.request("/wg/bluetooth/status", api.requestOptions("GET"), 8000).then(function (resultStatus) {
                adapterAvailable = resultStatus.available === true;
                var adapters = Array.isArray(resultStatus.adapters) ? resultStatus.adapters : [];
                setState(
                    adapterAvailable ? t("bluetoothAdapterReady") : t("bluetoothAdapterMissing"),
                    !adapterAvailable
                );
                detail.textContent = adapters.length
                    ? t("bluetoothAdapterCount", { count: adapters.length })
                    : t("bluetoothNoAdapterDetail");
                if (!adapterAvailable) {
                    pairedSection.hidden = false;
                    pairedDevices = [];
                    renderDevices(pairedList, pairedDevices, false);
                    pairedState.textContent = t("bluetoothNoPairedDevices");
                    return;
                }
                pairedSection.hidden = false;
                return api.request("/wg/bluetooth/devices", api.requestOptions("GET"), 12000).then(function (data) {
                    pairedDevices = Array.isArray(data.devices) ? data.devices : [];
                    renderDevices(pairedList, pairedDevices, false);
                    pairedState.textContent = pairedDevices.length
                        ? t("bluetoothPairedCount", { count: pairedDevices.length })
                        : t("bluetoothNoPairedDevices");
                });
            });
        }).catch(function (error) {
            serviceAvailable = false;
            adapterAvailable = false;
            setState(t("bluetoothLoadFailed"), true);
            detail.textContent = error.message || t("unknownError");
        }).then(function () {
            busy = false;
            updateControls();
        });
    }

    function scanForDevices() {
        if (busy || !serviceAvailable || !adapterAvailable) return Promise.resolve();
        busy = true;
        nearbySection.hidden = false;
        nearbyList.textContent = "";
        nearbyState.textContent = t("bluetoothScanning");
        setNotice("", false);
        updateControls();
        return api.request("/wg/bluetooth/scan", api.requestOptions("GET"), 18000).then(function (data) {
            nearbyDevices = Array.isArray(data.devices) ? data.devices : [];
            renderDevices(nearbyList, nearbyDevices, true);
            nearbyState.textContent = nearbyDevices.length
                ? t("bluetoothNearbyCount", { count: nearbyDevices.length })
                : t("bluetoothScanEmpty");
        }).catch(function (error) {
            nearbyState.textContent = t("bluetoothScanFailed");
            setNotice(error.message || t("unknownError"), true);
        }).then(function () {
            busy = false;
            updateControls();
        });
    }

    function pairDevice(device) {
        if (busy) return Promise.resolve();
        busy = true;
        setNotice(t("bluetoothPairing", { name: device.name }), false);
        updateControls();
        return api.request(
            "/wg/bluetooth/pair",
            api.requestOptions("POST", { address: device.address }),
            60000
        ).then(function () {
            setNotice(t("bluetoothPairSuccess", { name: device.name }), false);
            return loadBluetooth(false).then(scanForDevices);
        }).catch(function (error) {
            busy = false;
            setNotice(error.message || t("bluetoothPairFailed"), true);
            updateControls();
        });
    }

    function unpairDevice(device) {
        if (busy || !window.confirm(t("bluetoothUnpairConfirm", { name: device.name }))) return Promise.resolve();
        busy = true;
        setNotice(t("bluetoothUnpairing", { name: device.name }), false);
        updateControls();
        return api.request(
            "/wg/bluetooth/unpair",
            api.requestOptions("POST", { address: device.address }),
            15000
        ).then(function () {
            setNotice(t("bluetoothUnpairSuccess", { name: device.name }), false);
            return loadBluetooth(false);
        }).catch(function (error) {
            busy = false;
            setNotice(error.message || t("bluetoothUnpairFailed"), true);
            updateControls();
        });
    }

    function connectBle() {
        if (busy) return;
        if (bleDevice && bleDevice.gatt && bleDevice.gatt.connected) {
            bleDevice.gatt.disconnect();
            return;
        }
        busy = true;
        updateControls();
        setNotice("", false);
        navigator.bluetooth.requestDevice({ acceptAllDevices: true }).then(function (device) {
            bleDevice = device;
            if (!device.gatt) throw new Error(t("bluetoothBleUnsupported"));
            device.addEventListener("gattserverdisconnected", function () {
                setState(t("bluetoothBleDisconnected"), false);
                detail.textContent = t("bluetoothWebFallback");
                bleButton.textContent = t("bluetoothBleConnect");
                bleDevice = null;
            });
            return device.gatt.connect();
        }).then(function () {
            setState(t("bluetoothBleConnected"), false);
            detail.textContent = t("bluetoothBleSession", { name: bleDevice.name || bleDevice.id });
            bleButton.textContent = t("bluetoothBleDisconnect");
        }).catch(function (error) {
            if (error.name !== "NotFoundError") {
                setNotice(error.message || t("bluetoothBleFailed"), true);
            }
        }).then(function () {
            busy = false;
            updateControls();
        });
    }

    refreshButton.addEventListener("click", function () { loadBluetooth(true); });
    scanButton.addEventListener("click", scanForDevices);
    bleButton.addEventListener("click", connectBle);
    if (panel === "all" && refreshServerButton) {
        refreshServerButton.addEventListener("click", function () { loadBluetooth(true); });
    }
    loadBluetooth(false);
})();
