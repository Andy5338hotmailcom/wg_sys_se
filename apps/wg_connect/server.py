#!/usr/bin/env python3
"""Loopback-only WiFi and Bluetooth helper for Wildgoose."""

import argparse
import ctypes
import ipaddress
import json
import locale
import os
import platform
import re
import secrets
import subprocess
import tempfile
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


HOST = "127.0.0.1"
PORT = 8554

class MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_uint32),
        ("dwMemoryLoad", ctypes.c_uint32),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]


def read_memory_load():
    """物理内存占用百分比（0-100），读不到返回 None。"""
    if platform.system() != "Windows":
        return None
    try:
        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(MemoryStatusEx)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return float(status.dwMemoryLoad)
    except (AttributeError, OSError, ValueError):
        return None


class LoadGovernor:
    """按自身 CPU、内存占用与请求速率，给出建议的客户端轮询间隔（毫秒）。

    忙起来就把窗口结算成慢档，随正常响应顺手带回去，前端看到自己降速，界面上不做任何提示。
    """

    FAST_MS = 1000
    SLOW_MS = 15000

    def __init__(self, window_seconds=10.0, cpu_ratio=0.7, memory_percent=90.0, max_rps=10.0):
        self.window_seconds = window_seconds
        self.cpu_ratio = cpu_ratio
        self.memory_percent = memory_percent
        self.max_rps = max_rps
        self.lock = threading.Lock()
        self.window_start = time.monotonic()
        self.cpu_start = time.process_time()
        self.calls = 0
        self.slow = False

    def suggest(self):
        with self.lock:
            self.calls += 1
            elapsed = time.monotonic() - self.window_start
            if elapsed >= self.window_seconds:
                cpu_used = time.process_time() - self.cpu_start
                memory = read_memory_load()
                self.slow = bool(
                    (cpu_used / elapsed) >= self.cpu_ratio
                    or (memory is not None and memory >= self.memory_percent)
                    or (self.calls / elapsed) >= self.max_rps
                )
                self.window_start = time.monotonic()
                self.cpu_start = time.process_time()
                self.calls = 0
            return self.SLOW_MS if self.slow else self.FAST_MS


POLL_GOVERNOR = LoadGovernor()
DEFAULT_ALLOWED_ORIGINS = {"https://andy5338hotmailcom.github.io"}
PROFILE_NS = "http://www.microsoft.com/networking/WLAN/profile/v1"
WLAN_OPCODE_RADIO_STATE = 4
DOT11_RADIO_OFF = 0
DOT11_RADIO_ON = 1
ET.register_namespace("", PROFILE_NS)


class WlanGuid(ctypes.Structure):
    _fields_ = [
        ("data1", ctypes.c_uint32),
        ("data2", ctypes.c_uint16),
        ("data3", ctypes.c_uint16),
        ("data4", ctypes.c_uint8 * 8),
    ]


class WlanInterfaceInfo(ctypes.Structure):
    _fields_ = [
        ("guid", WlanGuid),
        ("description", ctypes.c_wchar * 256),
        ("state", ctypes.c_uint32),
    ]


class WlanInterfaceInfoListHeader(ctypes.Structure):
    _fields_ = [("number_of_items", ctypes.c_uint32), ("index", ctypes.c_uint32)]


class WlanRadioStateHeader(ctypes.Structure):
    _fields_ = [("number_of_phys", ctypes.c_uint32)]


class WlanRadioStateEntry(ctypes.Structure):
    _fields_ = [
        ("phy_index", ctypes.c_uint32),
        ("software_state", ctypes.c_uint32),
        ("hardware_state", ctypes.c_uint32),
    ]


class BluetoothAddress(ctypes.Union):
    _fields_ = [("ullLong", ctypes.c_uint64), ("bytes", ctypes.c_uint8 * 8)]


class BluetoothFindRadioParams(ctypes.Structure):
    _fields_ = [("dwSize", ctypes.c_uint32)]


class BluetoothRadioInfo(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint32),
        ("address", BluetoothAddress),
        ("name", ctypes.c_wchar * 248),
        ("class_of_device", ctypes.c_uint32),
        ("lmp_subversion", ctypes.c_uint16),
        ("manufacturer", ctypes.c_uint16),
    ]


class BluetoothDeviceSearchParams(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint32),
        ("return_authenticated", ctypes.c_int32),
        ("return_remembered", ctypes.c_int32),
        ("return_unknown", ctypes.c_int32),
        ("return_connected", ctypes.c_int32),
        ("issue_inquiry", ctypes.c_int32),
        ("timeout_multiplier", ctypes.c_uint8),
        ("radio", ctypes.c_void_p),
    ]


class SystemTime(ctypes.Structure):
    _fields_ = [
        ("year", ctypes.c_uint16),
        ("month", ctypes.c_uint16),
        ("day_of_week", ctypes.c_uint16),
        ("day", ctypes.c_uint16),
        ("hour", ctypes.c_uint16),
        ("minute", ctypes.c_uint16),
        ("second", ctypes.c_uint16),
        ("milliseconds", ctypes.c_uint16),
    ]


class BluetoothDeviceInfo(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint32),
        ("address", BluetoothAddress),
        ("class_of_device", ctypes.c_uint32),
        ("connected", ctypes.c_int32),
        ("remembered", ctypes.c_int32),
        ("authenticated", ctypes.c_int32),
        ("last_seen", SystemTime),
        ("last_used", SystemTime),
        ("name", ctypes.c_wchar * 248),
    ]


class ApiError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def decode_netsh(data):
    encodings = []
    preferred = locale.getpreferredencoding(False)
    if preferred:
        encodings.append(preferred)
    encodings.extend(["utf-8", "cp936", "cp950", "cp932", "cp1252"])
    markers = ("SSID", "Authentication", "Signal", "身份验证", "身份驗證", "信号", "訊號")
    candidates = []
    for encoding in dict.fromkeys(encodings):
        try:
            text = data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
        score = sum(text.count(marker) for marker in markers)
        candidates.append((score, text))
    if candidates:
        return max(candidates, key=lambda candidate: candidate[0])[1]
    return data.decode("utf-8", errors="replace")


def run_netsh(arguments, timeout=12):
    if platform.system() != "Windows":
        raise ApiError(501, "windows_only", "本地 WiFi 后端目前仅支持 Windows。")
    try:
        result = subprocess.run(
            ["netsh", "wlan"] + arguments,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        raise ApiError(501, "netsh_missing", "未找到 Windows netsh 工具。")
    except subprocess.TimeoutExpired:
        raise ApiError(504, "netsh_timeout", "Windows 无线网络操作超时，请重试。")
    output = decode_netsh(result.stdout + b"\n" + result.stderr).strip()
    if result.returncode != 0:
        raise ApiError(502, "netsh_failed", output or "Windows 无线网络操作失败。")
    return output


def parse_interface_connections(output):
    interfaces = []
    current = None

    def finish():
        if current and (current["state"] or current["ssid"] or current["guid"]):
            interfaces.append(current.copy())

    for line in output.splitlines():
        match = re.match(r"^\s*(?:Name|名称|名稱)\s*:\s*(.*?)\s*$", line, re.IGNORECASE)
        if match:
            finish()
            current = {"name": match.group(1), "guid": "", "state": "", "ssid": ""}
            continue
        if current is None:
            current = {"name": "", "guid": "", "state": "", "ssid": ""}
        match = re.match(r"^\s*(?:State|状态|狀態)\s*:\s*(.*?)\s*$", line, re.IGNORECASE)
        if match:
            current["state"] = match.group(1).casefold()
            continue
        match = re.match(r"^\s*SSID\s*:\s*(.*?)\s*$", line, re.IGNORECASE)
        if match:
            current["ssid"] = match.group(1)
            continue
        match = re.match(r"^\s*GUID\s*:\s*\{?([0-9a-fA-F-]{36})\}?\s*$", line, re.IGNORECASE)
        if match:
            current["guid"] = match.group(1).casefold()
    finish()
    return interfaces


def connected_ssids_from_output(output):
    connected_states = ("connected", "已连接", "已連線", "已連接")
    return list(dict.fromkeys(
        interface["ssid"]
        for interface in parse_interface_connections(output)
        if interface["state"] in connected_states and interface["ssid"]
    ))


def connected_ssid_from_output(output):
    ssids = connected_ssids_from_output(output)
    return ssids[0] if ssids else None


def network_mode(authentication, encryption):
    auth = authentication.casefold()
    cipher = encryption.casefold()
    if any(value in auth for value in ("open", "开放", "開放")):
        return "open"
    if "enterprise" in auth or "企业" in auth or "企業" in auth:
        return "unsupported"
    if "wpa3" in auth:
        return "wpa3"
    if "wpa2" in auth and any(value in auth for value in ("personal", "psk", "个人", "個人")):
        return "wpa2"
    if "wpa-personal" in auth or "wpa-psk" in auth:
        return "wpa2"
    if not auth and any(value in cipher for value in ("none", "无", "無")):
        return "open"
    return "unsupported"


def parse_networks(output, connected_ssid=None):
    if isinstance(connected_ssid, str):
        connected_ssids = {connected_ssid}
    else:
        connected_ssids = set(connected_ssid or [])
    networks = []
    current = None

    def finish():
        if current and current["ssid"]:
            mode = network_mode(current["authentication"], current["encryption"])
            networks.append({
                "ssid": current["ssid"],
                "signal": current["signal"],
                "security": current["authentication"] or current["encryption"] or "未知",
                "connected": current["ssid"] in connected_ssids,
                "connectable": mode != "unsupported",
                "open": mode == "open",
                "mode": mode,
            })

    for line in output.splitlines():
        match = re.match(r"^\s*SSID\s+\d+\s*:\s*(.*?)\s*$", line, re.IGNORECASE)
        if match:
            finish()
            current = {
                "ssid": match.group(1),
                "signal": 0,
                "authentication": "",
                "encryption": "",
            }
            continue
        if current is None:
            continue
        match = re.match(r"^\s*(?:Authentication|身份验证|身份驗證)\s*:\s*(.*?)\s*$", line, re.IGNORECASE)
        if match:
            current["authentication"] = match.group(1)
            continue
        match = re.match(r"^\s*(?:Encryption|加密)\s*:\s*(.*?)\s*$", line, re.IGNORECASE)
        if match:
            current["encryption"] = match.group(1)
            continue
        match = re.match(r"^\s*(?:Signal|信号|訊號)\s*:\s*(\d+)\s*%?\s*$", line, re.IGNORECASE)
        if match:
            current["signal"] = max(current["signal"], min(100, int(match.group(1))))
    finish()

    deduplicated = {}
    for network in networks:
        previous = deduplicated.get(network["ssid"])
        if previous is None:
            deduplicated[network["ssid"]] = network
        else:
            previous["signal"] = max(previous["signal"], network["signal"])
            previous["connected"] = previous["connected"] or network["connected"]
    return sorted(deduplicated.values(), key=lambda network: (-network["signal"], network["ssid"].casefold()))


def scan_wifi():
    deadline = time.monotonic() + 14
    interface_output = run_netsh(
        ["show", "interfaces"],
        timeout=max(0.1, deadline - time.monotonic()),
    )
    connected_ssids = connected_ssids_from_output(interface_output)
    networks_output = run_netsh(
        ["show", "networks", "mode=bssid"],
        timeout=max(0.1, deadline - time.monotonic()),
    )
    return parse_networks(networks_output, connected_ssids), connected_ssids


def open_wlan_client():
    if platform.system() != "Windows":
        raise ApiError(501, "windows_only", "本地 WiFi 后端目前仅支持 Windows。")
    try:
        api = ctypes.WinDLL("wlanapi.dll", use_last_error=True)
    except (AttributeError, OSError):
        raise ApiError(501, "wlan_api_missing", "无法加载 Windows WLAN 服务接口。")
    from ctypes import wintypes

    api.WlanOpenHandle.argtypes = [
        wintypes.DWORD,
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.HANDLE),
    ]
    api.WlanOpenHandle.restype = wintypes.DWORD
    api.WlanCloseHandle.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    api.WlanCloseHandle.restype = wintypes.DWORD
    api.WlanEnumInterfaces.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    api.WlanEnumInterfaces.restype = wintypes.DWORD
    api.WlanQueryInterface.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(WlanGuid),
        wintypes.DWORD,
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(wintypes.DWORD),
    ]
    api.WlanQueryInterface.restype = wintypes.DWORD
    api.WlanSetInterface.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(WlanGuid),
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    api.WlanSetInterface.restype = wintypes.DWORD
    api.WlanDisconnect.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(WlanGuid),
        ctypes.c_void_p,
    ]
    api.WlanDisconnect.restype = wintypes.DWORD
    api.WlanFreeMemory.argtypes = [ctypes.c_void_p]
    api.WlanFreeMemory.restype = None

    negotiated_version = wintypes.DWORD()
    handle = wintypes.HANDLE()
    status = api.WlanOpenHandle(2, None, ctypes.byref(negotiated_version), ctypes.byref(handle))
    if status:
        raise_wlan_error(status, "打开 Windows WLAN 服务")
    return api, handle


def open_bluetooth_api():
    if platform.system() != "Windows":
        raise ApiError(501, "windows_only", "本地蓝牙后端目前仅支持 Windows。")
    try:
        api = ctypes.WinDLL("bthprops.cpl", use_last_error=True)
    except (AttributeError, OSError):
        raise ApiError(501, "bluetooth_api_missing", "无法加载 Windows 蓝牙服务接口。")

    api.BluetoothFindFirstRadio.argtypes = [
        ctypes.POINTER(BluetoothFindRadioParams),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    api.BluetoothFindFirstRadio.restype = ctypes.c_void_p
    api.BluetoothFindNextRadio.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    api.BluetoothFindNextRadio.restype = ctypes.c_int32
    api.BluetoothFindRadioClose.argtypes = [ctypes.c_void_p]
    api.BluetoothFindRadioClose.restype = ctypes.c_int32
    api.BluetoothGetRadioInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(BluetoothRadioInfo),
    ]
    api.BluetoothGetRadioInfo.restype = ctypes.c_uint32
    api.BluetoothFindFirstDevice.argtypes = [
        ctypes.POINTER(BluetoothDeviceSearchParams),
        ctypes.POINTER(BluetoothDeviceInfo),
    ]
    api.BluetoothFindFirstDevice.restype = ctypes.c_void_p
    api.BluetoothFindNextDevice.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(BluetoothDeviceInfo),
    ]
    api.BluetoothFindNextDevice.restype = ctypes.c_int32
    api.BluetoothFindDeviceClose.argtypes = [ctypes.c_void_p]
    api.BluetoothFindDeviceClose.restype = ctypes.c_int32
    api.BluetoothAuthenticateDeviceEx.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(BluetoothDeviceInfo),
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]
    api.BluetoothAuthenticateDeviceEx.restype = ctypes.c_uint32
    api.BluetoothRemoveDevice.argtypes = [ctypes.POINTER(BluetoothAddress)]
    api.BluetoothRemoveDevice.restype = ctypes.c_uint32
    return api


def bluetooth_error(status, action):
    if status == 5:
        raise ApiError(403, "bluetooth_access_denied", action + "被 Windows 拒绝。")
    if status == 1168:
        raise ApiError(404, "bluetooth_device_not_found", "Windows 找不到该蓝牙设备。")
    raise ApiError(
        502,
        "bluetooth_operation_failed",
        action + "失败（Windows 蓝牙错误 " + str(status) + "）。",
    )


def enumerate_bluetooth_radios(api):
    params = BluetoothFindRadioParams()
    params.dwSize = ctypes.sizeof(params)
    radio = ctypes.c_void_p()
    search = api.BluetoothFindFirstRadio(ctypes.byref(params), ctypes.byref(radio))
    if not search:
        error = ctypes.get_last_error()
        if error in (0, 259):
            return []
        bluetooth_error(error, "查找蓝牙适配器")

    radios = []
    try:
        while radio.value:
            info = BluetoothRadioInfo()
            info.dwSize = ctypes.sizeof(info)
            status = api.BluetoothGetRadioInfo(radio, ctypes.byref(info))
            if status:
                close_bluetooth_radio_handle(radio)
                bluetooth_error(status, "读取蓝牙适配器")
            radios.append({
                "handle": radio,
                "name": info.name,
                "address": format_bluetooth_address(info.address.ullLong),
            })
            radio = ctypes.c_void_p()
            if not api.BluetoothFindNextRadio(search, ctypes.byref(radio)):
                error = ctypes.get_last_error()
                if error not in (0, 259):
                    bluetooth_error(error, "枚举蓝牙适配器")
                break
        return radios
    except Exception:
        for item in radios:
            close_bluetooth_radio_handle(item["handle"])
        raise
    finally:
        api.BluetoothFindRadioClose(search)


def close_bluetooth_radios(radios):
    for radio in radios:
        close_bluetooth_radio_handle(radio["handle"])


def close_bluetooth_radio_handle(handle):
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int32
    kernel32.CloseHandle(handle)


def format_bluetooth_address(address):
    digits = "{:012X}".format(address & 0xFFFFFFFFFFFF)
    return ":".join(digits[index:index + 2] for index in range(0, 12, 2))


def normalize_bluetooth_address(address):
    if not isinstance(address, str):
        raise ApiError(400, "invalid_bluetooth_address", "蓝牙设备地址格式无效。")
    compact = address.replace(":", "").replace("-", "")
    if not re.fullmatch(r"[0-9a-fA-F]{12}", compact):
        raise ApiError(400, "invalid_bluetooth_address", "蓝牙设备地址必须是 12 位十六进制 MAC 地址。")
    return compact.upper()


def get_bluetooth_status():
    api = open_bluetooth_api()
    radios = enumerate_bluetooth_radios(api)
    try:
        return {
            "available": bool(radios),
            "adapters": [
                {"name": radio["name"] or "Bluetooth", "address": radio["address"]}
                for radio in radios
            ],
        }
    finally:
        close_bluetooth_radios(radios)


def list_bluetooth_devices(scan=False):
    api = open_bluetooth_api()
    radios = enumerate_bluetooth_radios(api)
    if not radios:
        return []
    params = BluetoothDeviceSearchParams()
    params.dwSize = ctypes.sizeof(params)
    params.return_authenticated = 1
    params.return_remembered = 1
    params.return_unknown = int(scan)
    params.return_connected = 1
    params.issue_inquiry = int(scan)
    params.timeout_multiplier = 8 if scan else 0
    params.radio = radios[0]["handle"]
    info = BluetoothDeviceInfo()
    info.dwSize = ctypes.sizeof(info)
    search = api.BluetoothFindFirstDevice(ctypes.byref(params), ctypes.byref(info))
    if not search:
        error = ctypes.get_last_error()
        close_bluetooth_radios(radios)
        if error in (0, 259):
            return []
        bluetooth_error(error, "扫描蓝牙设备" if scan else "读取已配对蓝牙设备")

    devices = []
    seen = set()
    try:
        while True:
            address = format_bluetooth_address(info.address.ullLong)
            if address not in seen and (scan or info.authenticated):
                seen.add(address)
                devices.append({
                    "address": address,
                    "name": info.name or address,
                    "paired": bool(info.authenticated),
                    "remembered": bool(info.remembered),
                })
            info = BluetoothDeviceInfo()
            info.dwSize = ctypes.sizeof(info)
            if not api.BluetoothFindNextDevice(search, ctypes.byref(info)):
                error = ctypes.get_last_error()
                if error not in (0, 259):
                    bluetooth_error(error, "扫描蓝牙设备" if scan else "读取已配对蓝牙设备")
                break
        return devices
    finally:
        api.BluetoothFindDeviceClose(search)
        close_bluetooth_radios(radios)


def pair_bluetooth_device(address):
    normalized = normalize_bluetooth_address(address)
    api = open_bluetooth_api()
    radios = enumerate_bluetooth_radios(api)
    if not radios:
        raise ApiError(404, "bluetooth_adapter_missing", "没有检测到可用的蓝牙适配器。")
    try:
        device = BluetoothDeviceInfo()
        device.dwSize = ctypes.sizeof(device)
        device.address.ullLong = int(normalized, 16)
        status = api.BluetoothAuthenticateDeviceEx(
            None,
            radios[0]["handle"],
            ctypes.byref(device),
            None,
            0,
        )
        if status:
            bluetooth_error(status, "配对蓝牙设备")
        return {"paired": True, "address": format_bluetooth_address(device.address.ullLong)}
    finally:
        close_bluetooth_radios(radios)


def unpair_bluetooth_device(address):
    normalized = normalize_bluetooth_address(address)
    api = open_bluetooth_api()
    device_address = BluetoothAddress()
    device_address.ullLong = int(normalized, 16)
    status = api.BluetoothRemoveDevice(ctypes.byref(device_address))
    if status:
        bluetooth_error(status, "移除蓝牙设备")
    return {"removed": True, "address": format_bluetooth_address(device_address.ullLong)}


def raise_wlan_error(status, action):
    if status == 5:
        raise ApiError(403, "admin_required", action + "被拒绝，请使用管理员权限运行本地服务。")
    if status == 1062:
        raise ApiError(503, "wlan_service_stopped", "Windows WLAN AutoConfig 服务未运行。")
    raise ApiError(502, "wlan_operation_failed", action + "失败（Windows WLAN 错误 " + str(status) + "）。")


def enum_wlan_interfaces(api, handle):
    interface_list = ctypes.c_void_p()
    status = api.WlanEnumInterfaces(handle, None, ctypes.byref(interface_list))
    if status:
        raise_wlan_error(status, "枚举无线网卡")
    try:
        header = ctypes.cast(interface_list, ctypes.POINTER(WlanInterfaceInfoListHeader)).contents
        first_item = ctypes.sizeof(WlanInterfaceInfoListHeader)
        item_size = ctypes.sizeof(WlanInterfaceInfo)
        items = []
        for index in range(header.number_of_items):
            address = interface_list.value + first_item + index * item_size
            info = ctypes.cast(address, ctypes.POINTER(WlanInterfaceInfo)).contents
            guid_bytes = ctypes.string_at(ctypes.byref(info.guid), ctypes.sizeof(WlanGuid))
            items.append({
                "guid": WlanGuid.from_buffer_copy(guid_bytes),
                "description": info.description,
                "state": info.state,
            })
        return items
    finally:
        api.WlanFreeMemory(interface_list)


def query_radio_state(api, handle, guid):
    from ctypes import wintypes

    size = wintypes.DWORD()
    data = ctypes.c_void_p()
    value_type = wintypes.DWORD()
    status = api.WlanQueryInterface(
        handle,
        ctypes.byref(guid),
        WLAN_OPCODE_RADIO_STATE,
        None,
        ctypes.byref(size),
        ctypes.byref(data),
        ctypes.byref(value_type),
    )
    if status:
        raise_wlan_error(status, "读取无线网卡状态")
    keep_data = False
    try:
        if not data.value or size.value < ctypes.sizeof(WlanRadioStateHeader):
            raise ApiError(502, "invalid_wlan_state", "Windows 返回的无线网卡状态无效。")
        header = ctypes.cast(data, ctypes.POINTER(WlanRadioStateHeader)).contents
        required_size = ctypes.sizeof(WlanRadioStateHeader) + header.number_of_phys * ctypes.sizeof(WlanRadioStateEntry)
        if size.value < required_size:
            raise ApiError(502, "invalid_wlan_state", "Windows 返回的无线电状态数据不完整。")
        entries = []
        for index in range(header.number_of_phys):
            address = data.value + ctypes.sizeof(WlanRadioStateHeader) + index * ctypes.sizeof(WlanRadioStateEntry)
            entry = ctypes.cast(address, ctypes.POINTER(WlanRadioStateEntry)).contents
            entries.append({
                "software_on": entry.software_state == DOT11_RADIO_ON,
                "hardware_on": entry.hardware_state == DOT11_RADIO_ON,
            })
        keep_data = True
        return data, size.value, entries
    finally:
        if not keep_data:
            api.WlanFreeMemory(data)


def get_wifi_status():
    api, handle = open_wlan_client()
    try:
        adapters = enum_wlan_interfaces(api, handle)
        state_names = {
            0: "not_ready",
            1: "connected",
            2: "ad_hoc",
            3: "disconnecting",
            4: "disconnected",
            5: "associating",
            6: "discovering",
            7: "authenticating",
        }
        interfaces = []
        for adapter in adapters:
            data, _, radios = query_radio_state(api, handle, adapter["guid"])
            api.WlanFreeMemory(data)
            interfaces.append({
                "description": adapter["description"],
                "state": state_names.get(adapter["state"], "unknown"),
                "enabled": bool(radios) and all(radio["software_on"] and radio["hardware_on"] for radio in radios),
            })
        return {
            "available": bool(interfaces),
            "enabled": bool(interfaces) and all(interface["enabled"] for interface in interfaces),
            "interfaces": interfaces,
        }
    finally:
        api.WlanCloseHandle(handle, None)

class SystemPowerStatus(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_ubyte),
        ("BatteryFlag", ctypes.c_ubyte),
        ("BatteryLifePercent", ctypes.c_ubyte),
        ("SystemStatusFlag", ctypes.c_ubyte),
        ("BatteryLifeTime", ctypes.c_uint32),
        ("BatteryFullLifeTime", ctypes.c_uint32),
    ]


def get_power_status():
    if platform.system() != "Windows":
        raise ApiError(501, "not_supported", "只有 Windows 能读取电源状态。")
    status = SystemPowerStatus()
    try:
        ok = ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status))
    except (AttributeError, OSError):
        raise ApiError(500, "power_unavailable", "读取电源状态失败。")
    if not ok:
        raise ApiError(500, "power_unavailable", "读取电源状态失败。")
    flag = status.BatteryFlag
    percent = status.BatteryLifePercent
    if percent > 100:
        percent = None
    has_battery = not bool(flag & 128)
    charging = bool(flag & 8)
    ac_status = {0: "battery", 1: "ac", 255: "unknown"}.get(status.ACLineStatus, "unknown")
    minutes_left = status.BatteryLifeTime
    if minutes_left == 0xFFFFFFFF or not has_battery or charging or percent is None:
        minutes_left = None
    else:
        minutes_left = minutes_left // 60
    return {
        "percent": percent,
        "charging": charging,
        "has_battery": has_battery,
        "ac_status": ac_status,
        "minutes_left": minutes_left,
    }


def set_wifi_enabled(enabled):
    if not isinstance(enabled, bool):
        raise ApiError(400, "invalid_enabled_value", "WiFi 开关状态无效。")
    api, handle = open_wlan_client()
    try:
        adapters = enum_wlan_interfaces(api, handle)
        if not adapters:
            raise ApiError(404, "wifi_adapter_missing", "系统没有可用的无线网卡。")
        for adapter in adapters:
            data, size, radios = query_radio_state(api, handle, adapter["guid"])
            try:
                if not radios:
                    continue
                for index in range(len(radios)):
                    address = data.value + ctypes.sizeof(WlanRadioStateHeader) + index * ctypes.sizeof(WlanRadioStateEntry)
                    entry = ctypes.cast(address, ctypes.POINTER(WlanRadioStateEntry)).contents
                    entry.software_state = DOT11_RADIO_ON if enabled else DOT11_RADIO_OFF
                status = api.WlanSetInterface(
                    handle,
                    ctypes.byref(adapter["guid"]),
                    WLAN_OPCODE_RADIO_STATE,
                    size,
                    data,
                    None,
                )
                if status:
                    raise_wlan_error(status, "切换 WiFi")
            finally:
                api.WlanFreeMemory(data)
    finally:
        api.WlanCloseHandle(handle, None)

    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        state = get_wifi_status()
        if state["available"] and state["enabled"] == enabled:
            return state
        time.sleep(0.5)
    raise ApiError(409, "wifi_state_mismatch", "系统没有切换到请求的 WiFi 状态，请检查硬件开关或无线网卡。")


def disconnect_wifi(ssid):
    validate_ssid(ssid)
    connected_interfaces = [
        interface for interface in parse_interface_connections(run_netsh(["show", "interfaces"]))
        if interface["state"] in ("connected", "已连接", "已連線", "已連接")
        and interface["ssid"] == ssid
    ]
    if not connected_interfaces:
        raise ApiError(409, "wifi_not_connected", "该 WiFi 当前未连接。")
    if any(not interface["guid"] for interface in connected_interfaces):
        raise ApiError(502, "wifi_interface_unknown", "Windows 未提供该 WiFi 网卡的接口标识，无法安全断开。")

    api, handle = open_wlan_client()
    try:
        adapters = enum_wlan_interfaces(api, handle)
        adapters_by_guid = {
            str(uuid.UUID(bytes_le=ctypes.string_at(ctypes.byref(adapter["guid"]), ctypes.sizeof(WlanGuid)))).casefold(): adapter
            for adapter in adapters
        }
        for interface in connected_interfaces:
            adapter = adapters_by_guid.get(interface["guid"])
            if adapter is None:
                raise ApiError(502, "wifi_interface_unknown", "无法将已连接的 WiFi 映射到无线网卡。")
            status = api.WlanDisconnect(handle, ctypes.byref(adapter["guid"]), None)
            if status:
                raise_wlan_error(status, "断开 WiFi")
    finally:
        api.WlanCloseHandle(handle, None)

    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        still_connected = [
            interface for interface in parse_interface_connections(run_netsh(["show", "interfaces"]))
            if interface["state"] in ("connected", "已连接", "已連線", "已連接")
            and interface["ssid"] == ssid
        ]
        if not still_connected:
            return {"disconnected": True, "ssid": ssid}
        time.sleep(0.5)
    raise ApiError(504, "wifi_disconnect_timeout", "断开请求已发送，但系统仍报告该 WiFi 已连接。")


def make_profile(ssid, password, mode):
    root = ET.Element("{" + PROFILE_NS + "}WLANProfile")
    ET.SubElement(root, "{" + PROFILE_NS + "}name").text = ssid
    ssid_config = ET.SubElement(root, "{" + PROFILE_NS + "}SSIDConfig")
    ssid_element = ET.SubElement(ssid_config, "{" + PROFILE_NS + "}SSID")
    ET.SubElement(ssid_element, "{" + PROFILE_NS + "}name").text = ssid
    ET.SubElement(root, "{" + PROFILE_NS + "}connectionType").text = "ESS"
    ET.SubElement(root, "{" + PROFILE_NS + "}connectionMode").text = "auto"
    msm = ET.SubElement(root, "{" + PROFILE_NS + "}MSM")
    security = ET.SubElement(msm, "{" + PROFILE_NS + "}security")
    auth = ET.SubElement(security, "{" + PROFILE_NS + "}authEncryption")
    ET.SubElement(auth, "{" + PROFILE_NS + "}authentication").text = {
        "open": "open",
        "wpa2": "WPA2PSK",
        "wpa3": "WPA3SAE",
    }[mode]
    ET.SubElement(auth, "{" + PROFILE_NS + "}encryption").text = "none" if mode == "open" else "AES"
    ET.SubElement(auth, "{" + PROFILE_NS + "}useOneX").text = "false"
    if mode != "open":
        shared_key = ET.SubElement(security, "{" + PROFILE_NS + "}sharedKey")
        ET.SubElement(shared_key, "{" + PROFILE_NS + "}keyType").text = "passPhrase"
        ET.SubElement(shared_key, "{" + PROFILE_NS + "}protected").text = "false"
        ET.SubElement(shared_key, "{" + PROFILE_NS + "}keyMaterial").text = password
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def validate_ssid(ssid):
    if not isinstance(ssid, str) or not ssid or len(ssid.encode("utf-8")) > 32:
        raise ApiError(400, "invalid_ssid", "SSID 必须为 1 到 32 个 UTF-8 字节。")
    if any(ord(char) < 32 or ord(char) == 127 for char in ssid):
        raise ApiError(400, "invalid_ssid", "SSID 不能包含控制字符。")
    if '"' in ssid:
        raise ApiError(400, "unsupported_ssid", "SSID 包含 Windows netsh 无法安全处理的引号。")


def validate_password(password, mode):
    if not isinstance(password, str):
        raise ApiError(400, "invalid_password", "WiFi 密码格式无效。")
    if mode == "open":
        if password:
            raise ApiError(400, "password_not_needed", "这是开放网络，不需要密码。")
        return
    if mode in ("wpa2", "wpa3") and (
        (8 <= len(password) <= 63 and all(0x20 <= ord(char) <= 0x7E for char in password))
        or (mode == "wpa2" and re.fullmatch(r"[0-9a-fA-F]{64}", password))
    ):
        return
    raise ApiError(400, "invalid_password", "WiFi 密码长度无效（WPA 密码为 8 到 63 个字符）。")


def connect_wifi(ssid, password):
    validate_ssid(ssid)
    if not isinstance(password, str) or len(password) > 128:
        raise ApiError(400, "invalid_password", "WiFi 密码长度无效。")
    networks, _ = scan_wifi()
    network = next((item for item in networks if item["ssid"] == ssid), None)
    if network is None:
        raise ApiError(404, "network_not_found", "没有找到该 WiFi，请重新扫描后再试。")
    mode = network["mode"]
    if mode == "unsupported":
        raise ApiError(400, "unsupported_security", "暂不支持此网络的安全类型（例如企业认证网络）。")
    validate_password(password, mode)

    profile = make_profile(ssid, password, mode)
    try:
        with tempfile.TemporaryDirectory(prefix="wg-connect-") as directory:
            profile_path = os.path.join(directory, "wifi-profile.xml")
            with open(profile_path, "wb") as profile_file:
                profile_file.write(profile)
            run_netsh(["add", "profile", 'filename="' + profile_path + '"', "user=current"])
        run_netsh(['connect', 'name="' + ssid + '"', 'ssid="' + ssid + '"'], timeout=15)
    except ApiError:
        raise
    except OSError:
        raise ApiError(500, "profile_error", "无法创建临时 WiFi 配置文件。")

    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        connected = connected_ssids_from_output(run_netsh(["show", "interfaces"]))
        if ssid in connected:
            return {"connected": True, "ssid": ssid}
        time.sleep(1)
    raise ApiError(504, "connection_timeout", "已请求连接，但系统未能在 15 秒内确认连接。")


def is_allowed_origin(origin, configured_origins, allow_file_origin=False):
    if not origin:
        return False
    if origin == "null":
        return allow_file_origin
    if origin in configured_origins:
        return True
    try:
        parsed = urlsplit(origin)
        if parsed.scheme not in ("http", "https") or parsed.username or parsed.password:
            return False
        if parsed.path or parsed.query or parsed.fragment:
            return False
        address = parsed.hostname
        if not address:
            return False
        return address.casefold() == "localhost" or ipaddress.ip_address(address).is_loopback
    except ValueError:
        return False


def is_promptable_origin(origin):
    if not isinstance(origin, str) or not origin or origin == "null" or len(origin) > 2048:
        return False
    if any(ord(char) < 32 or ord(char) == 127 for char in origin):
        return False
    try:
        parsed = urlsplit(origin)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            return False
        if parsed.netloc != parsed.netloc.strip():
            return False
        _ = parsed.port
        return True
    except ValueError:
        return False


def confirm_origin_access(origin):
    if platform.system() != "Windows":
        return False
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
    except (AttributeError, OSError):
        raise ApiError(503, "origin_prompt_unavailable", "无法显示来源授权窗口；请求已拒绝。")

    user32.MessageBoxW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_uint,
    ]
    user32.MessageBoxW.restype = ctypes.c_int
    message = (
        "网页来源：\n" + origin +
        "\n\n该网页请求管理此电脑的 WiFi 和蓝牙（扫描、连接或断开、切换 WiFi、配对或移除设备）。"
        "\n选择“是”仅允许此来源访问，直到本地服务退出；选择“否”将拒绝请求。"
        "\n若页面已显示服务不可用，批准后请点击“重新检测服务器”。"
    )
    flags = 0x00000004 | 0x00000030 | 0x00000100 | 0x00040000 | 0x00010000
    result = user32.MessageBoxW(
        None,
        message,
        "Wildgoose 连接中心 - 新来源授权",
        flags,
    )
    if result == 0:
        raise ApiError(503, "origin_prompt_failed", "来源授权窗口未能显示；请求已拒绝。")
    return result == 6


class WifiServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, configured_origins, allow_file_origin=True):
        super().__init__(address, handler)
        self.configured_origins = set(configured_origins)
        self.allow_file_origin = allow_file_origin
        self.tokens = {}
        self.token_lock = threading.Lock()
        self.origin_decisions = {}
        self.origin_lock = threading.Lock()

    def authorize_origin(self, origin, allow_prompt=True):
        if is_allowed_origin(
            origin,
            self.configured_origins,
            self.allow_file_origin,
        ):
            return True
        with self.origin_lock:
            if origin in self.origin_decisions:
                return self.origin_decisions[origin]
            if not allow_prompt or not is_promptable_origin(origin):
                return False
            self.origin_decisions[origin] = confirm_origin_access(origin)
            return self.origin_decisions[origin]

    def issue_token(self, origin):
        now = time.monotonic()
        with self.token_lock:
            self.tokens = {
                token: value for token, value in self.tokens.items()
                if value[1] > now
            }
            token = secrets.token_urlsafe(32)
            self.tokens[token] = (origin, now + 90)
        return token

    def consume_token(self, token, origin):
        now = time.monotonic()
        with self.token_lock:
            value = self.tokens.pop(token, None)
        return value is not None and value[0] == origin and value[1] > now


GET_ENDPOINTS = frozenset((
    "/wg/ping",
    "/wg/power",
    "/wg/wifi/status",
    "/wg/wifi/scan",
    "/wg/bluetooth/status",
    "/wg/bluetooth/devices",
    "/wg/bluetooth/scan",
))
POST_ENDPOINTS = frozenset((
    "/wg/wifi/connect",
    "/wg/wifi/toggle",
    "/wg/wifi/disconnect",
    "/wg/bluetooth/pair",
    "/wg/bluetooth/unpair",
))


class WifiHandler(BaseHTTPRequestHandler):
    server_version = "WG-Connect/1.2"

    def log_message(self, format_string, *args):
        # Never log request bodies: the connect request contains a WiFi password.
        super().log_message(format_string, *args)

    def get_allowed_origin(self):
        origin = self.headers.get("Origin", "")
        try:
            allowed = self.server.authorize_origin(
                origin,
                allow_prompt=self.path in (GET_ENDPOINTS | POST_ENDPOINTS),
            )
        except ApiError as error:
            self.send_json(error.status, {"error": error.code, "message": error.message})
            return None
        if not allowed:
            self.send_json(403, {"error": "origin_denied", "message": "请求来源未获允许。"})
            return None
        return origin

    def send_json(self, status, body, origin=None, token=None):
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Access-Control-Expose-Headers", "X-WG-Token")
            self.send_header("Vary", "Origin")
        if token:
            self.send_header("X-WG-Token", token)
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        origin = self.get_allowed_origin()
        if origin is None:
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-WG-Token")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "300")
        self.send_header("Vary", "Origin")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        origin = self.get_allowed_origin()
        if origin is None:
            return
        if self.path == "/wg/ping":
            token = self.server.issue_token(origin)
            caps = ["wifi", "bluetooth", "power"] if platform.system() == "Windows" else []
            self.send_json(
                200,
                {"ok": True, "version": "1.2", "caps": caps, "poll_ms": POLL_GOVERNOR.suggest()},
                origin,
                token,
            )
            return
        if self.path not in GET_ENDPOINTS:
            self.send_json(404, {"error": "not_found", "message": "接口不存在。"}, origin)
            return
        if not self.server.consume_token(self.headers.get("X-WG-Token", ""), origin):
            self.send_json(403, {"error": "token_invalid", "message": "请求令牌无效或已使用，请重新加载页面。"}, origin)
            return
        token = self.server.issue_token(origin)
        try:
            if self.path == "/wg/wifi/status":
                self.send_json(200, get_wifi_status(), origin, token)
                return
            if self.path == "/wg/bluetooth/status":
                self.send_json(200, get_bluetooth_status(), origin, token)
                return
            if self.path == "/wg/bluetooth/devices":
                self.send_json(200, {"devices": list_bluetooth_devices()}, origin, token)
                return
            if self.path == "/wg/bluetooth/scan":
                self.send_json(200, {"devices": list_bluetooth_devices(scan=True)}, origin, token)
                return
            if self.path == "/wg/power":
                self.send_json(
                    200,
                    {"ok": True, **get_power_status(), "poll_ms": POLL_GOVERNOR.suggest()},
                    origin,
                    token,
                )
                return
            networks, connected_ssids = scan_wifi()
            self.send_json(
                200,
                {
                    "networks": networks,
                    "connected_ssid": connected_ssids[0] if connected_ssids else None,
                    "connected_ssids": connected_ssids,
                },
                origin,
                token,
            )
        except ApiError as error:
            self.send_json(error.status, {"error": error.code, "message": error.message}, origin, token)

    def do_POST(self):
        origin = self.get_allowed_origin()
        if origin is None:
            return
        if self.path not in POST_ENDPOINTS:
            self.send_json(404, {"error": "not_found", "message": "接口不存在。"}, origin)
            return
        if not self.server.consume_token(self.headers.get("X-WG-Token", ""), origin):
            self.send_json(403, {"error": "token_invalid", "message": "请求令牌无效或已使用，请重新加载页面。"}, origin)
            return
        token = self.server.issue_token(origin)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 4096:
                raise ApiError(400, "invalid_request", "请求内容无效。")
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise ApiError(400, "invalid_request", "请求内容不是有效的 JSON。")
            if not isinstance(data, dict):
                raise ApiError(400, "invalid_request", "请求内容格式无效。")
            if self.path == "/wg/bluetooth/pair":
                result = pair_bluetooth_device(data.get("address"))
            elif self.path == "/wg/bluetooth/unpair":
                result = unpair_bluetooth_device(data.get("address"))
            elif self.path == "/wg/wifi/toggle":
                result = set_wifi_enabled(data.get("enabled"))
            elif self.path == "/wg/wifi/disconnect":
                result = disconnect_wifi(data.get("ssid"))
            else:
                result = connect_wifi(data.get("ssid"), data.get("password", ""))
            self.send_json(200, result, origin, token)
        except ApiError as error:
            self.send_json(error.status, {"error": error.code, "message": error.message}, origin, token)


def main():
    parser = argparse.ArgumentParser(description="Wildgoose loopback WiFi and Bluetooth service")
    parser.add_argument(
        "--allow-origin",
        action="append",
        default=[],
        help="allow this exact web origin (repeat for multiple origins)",
    )
    parser.add_argument(
        "--deny-file-origin",
        action="store_true",
        help="reject Origin: null from local files and opaque origins",
    )
    args = parser.parse_args()
    allowed_origins = DEFAULT_ALLOWED_ORIGINS.union(args.allow_origin)
    server = WifiServer(
        (HOST, PORT),
        WifiHandler,
        allowed_origins,
        allow_file_origin=not args.deny_file_origin,
    )
    print("WG connection service listening at http://127.0.0.1:8554")
    print("Allowed origins: loopback pages, default/configured origins, or user-approved origins")
    if server.allow_file_origin:
        print("WARNING: Origin: null is enabled for all local files and opaque origins.")
    else:
        print("Origin: null is disabled.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping WG WiFi service.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
