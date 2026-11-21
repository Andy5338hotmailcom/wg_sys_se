import os
import sys

# 允许从任意目录运行（包括本目录）：把仓库根加入 sys.path，才能 import apps.wg_connect。
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))

import unittest
import xml.etree.ElementTree as ET
import json
import ctypes
import threading
import urllib.error
import urllib.request
import uuid
from unittest.mock import patch

from apps.wg_connect import server as wifi_server
from apps.wg_connect.server import (
    PROFILE_NS,
    ApiError,
    connected_ssid_from_output,
    is_allowed_origin,
    make_profile,
    network_mode,
    parse_networks,
    validate_password,
    WifiHandler,
    WifiServer,
)


class WifiServerTests(unittest.TestCase):
    def test_parse_networks_groups_bssids_and_marks_connected(self):
        output = """\
SSID 1 : Cafe
    Authentication : WPA2-Personal
    Encryption : CCMP
    BSSID 1 : 00:11:22:33:44:55
         Signal : 42%
    BSSID 2 : 00:11:22:33:44:66
         Signal : 81%
SSID 2 : Guest
    Authentication : Open
    Encryption : None
    Signal : 55%
"""
        networks = parse_networks(output, "Cafe")
        self.assertEqual([network["ssid"] for network in networks], ["Cafe", "Guest"])
        self.assertEqual(networks[0]["signal"], 81)
        self.assertTrue(networks[0]["connected"])
        self.assertTrue(networks[1]["open"])

    def test_parse_localized_network_and_connected_interface(self):
        networks = parse_networks(
            "SSID 1 : 家庭网络\n    身份验证 : WPA2-个人\n    加密 : CCMP\n    信号 : 76%\n"
        )
        self.assertEqual(networks[0]["ssid"], "家庭网络")
        self.assertEqual(networks[0]["signal"], 76)
        self.assertTrue(networks[0]["connectable"])
        self.assertEqual(
            connected_ssid_from_output("    状态 : 已连接\n    SSID : 家庭网络\n"),
            "家庭网络",
        )

    def test_parse_multiple_connected_wifi_interfaces(self):
        output = """\
Name : Wi-Fi
    GUID : {11111111-2222-3333-4444-555555555555}
    State : connected
    SSID : Cafe
Name : Wi-Fi 2
    GUID : {aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee}
    State : connected
    SSID : Office
Name : Wi-Fi 3
    State : disconnected
"""
        self.assertEqual(
            wifi_server.connected_ssids_from_output(output),
            ["Cafe", "Office"],
        )

    def test_disconnect_targets_only_the_requested_ssid(self):
        cafe_guid = "11111111-2222-3333-4444-555555555555"
        office_guid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        before = (
            "Name : Wi-Fi\n"
            "    GUID : {" + cafe_guid + "}\n"
            "    State : connected\n"
            "    SSID : Cafe\n"
            "Name : Wi-Fi 2\n"
            "    GUID : {" + office_guid + "}\n"
            "    State : connected\n"
            "    SSID : Office\n"
        )
        after = (
            "Name : Wi-Fi\n"
            "    GUID : {" + cafe_guid + "}\n"
            "    State : disconnected\n"
            "Name : Wi-Fi 2\n"
            "    GUID : {" + office_guid + "}\n"
            "    State : connected\n"
            "    SSID : Office\n"
        )
        cafe_adapter = {
            "guid": wifi_server.WlanGuid.from_buffer_copy(uuid.UUID(cafe_guid).bytes_le),
            "description": "Cafe adapter",
            "state": 1,
        }
        office_adapter = {
            "guid": wifi_server.WlanGuid.from_buffer_copy(uuid.UUID(office_guid).bytes_le),
            "description": "Office adapter",
            "state": 1,
        }
        api = type("FakeWlanApi", (), {
            "WlanDisconnect": lambda *args: 0,
            "WlanCloseHandle": lambda *args: 0,
        })()
        with patch.object(wifi_server, "run_netsh", side_effect=[before, after]), \
                patch.object(wifi_server, "open_wlan_client", return_value=(api, object())), \
                patch.object(wifi_server, "enum_wlan_interfaces", return_value=[cafe_adapter, office_adapter]) as enumerate_adapters, \
                patch.object(api, "WlanDisconnect", wraps=api.WlanDisconnect) as disconnect:
            result = wifi_server.disconnect_wifi("Cafe")
        self.assertEqual(result, {"disconnected": True, "ssid": "Cafe"})
        self.assertEqual(disconnect.call_count, 1)
        disconnected_guid = disconnect.call_args.args[1]._obj
        self.assertEqual(
            ctypes.string_at(ctypes.byref(disconnected_guid), ctypes.sizeof(wifi_server.WlanGuid)),
            ctypes.string_at(ctypes.byref(cafe_adapter["guid"]), ctypes.sizeof(wifi_server.WlanGuid)),
        )
        self.assertEqual(enumerate_adapters.call_count, 1)

    def test_profile_xml_escapes_ssid_and_password(self):
        root = ET.fromstring(make_profile("A&B", "pass<&word", "wpa2"))
        ns = {"w": PROFILE_NS}
        self.assertEqual(root.findtext("w:name", namespaces=ns), "A&B")
        self.assertEqual(
            root.findtext(".//w:keyMaterial", namespaces=ns),
            "pass<&word",
        )

    def test_rejects_enterprise_networks_and_invalid_passwords(self):
        self.assertEqual(network_mode("WPA2-Enterprise", "CCMP"), "unsupported")
        with self.assertRaises(ApiError):
            validate_password("short", "wpa2")
        with self.assertRaises(ApiError):
            validate_password("密码密码密码", "wpa2")

    def test_normalizes_and_validates_bluetooth_addresses(self):
        self.assertEqual(
            wifi_server.normalize_bluetooth_address("a1-b2-c3-d4-e5-f6"),
            "A1B2C3D4E5F6",
        )
        self.assertEqual(
            wifi_server.format_bluetooth_address(0xA1B2C3D4E5F6),
            "A1:B2:C3:D4:E5:F6",
        )
        with self.assertRaises(ApiError):
            wifi_server.normalize_bluetooth_address("not-an-address")

    def test_origin_policy_requires_loopback_or_explicit_allowlist(self):
        self.assertTrue(is_allowed_origin("http://127.0.0.1:8000", set()))
        self.assertTrue(is_allowed_origin("http://localhost:3000", set()))
        self.assertFalse(is_allowed_origin("null", set()))
        self.assertTrue(is_allowed_origin("null", set(), allow_file_origin=True))
        self.assertFalse(is_allowed_origin("https://example.com", set()))
        self.assertTrue(is_allowed_origin("https://example.com", {"https://example.com"}))

    def test_http_scan_rotates_one_time_token(self):
        interface_output = "    State : connected\n    SSID : Cafe\n"
        networks_output = (
            "SSID 1 : Cafe\n"
            "    Authentication : WPA2-Personal\n"
            "    Encryption : CCMP\n"
            "    Signal : 75%\n"
        )
        http_server = WifiServer(("127.0.0.1", 0), WifiHandler, set())
        thread = threading.Thread(target=http_server.serve_forever, daemon=True)
        thread.start()
        base_url = "http://127.0.0.1:" + str(http_server.server_port)
        try:
            with patch.object(wifi_server, "run_netsh", side_effect=[interface_output, networks_output]):
                ping = urllib.request.urlopen(urllib.request.Request(
                    base_url + "/wg/ping",
                    headers={"Origin": "http://localhost:8000"},
                ))
                original_token = ping.headers["X-WG-Token"]
                self.assertEqual(json.loads(ping.read())["caps"], ["wifi", "bluetooth"])

                scan = urllib.request.urlopen(urllib.request.Request(
                    base_url + "/wg/wifi/scan",
                    headers={
                        "Origin": "http://localhost:8000",
                        "X-WG-Token": original_token,
                    },
                ))
                next_token = scan.headers["X-WG-Token"]
                result = json.loads(scan.read())
                self.assertNotEqual(original_token, next_token)
                self.assertTrue(result["networks"][0]["connected"])
                self.assertEqual(scan.headers["Access-Control-Allow-Private-Network"], "true")
                self.assertIn("X-WG-Token", scan.headers["Access-Control-Expose-Headers"])

            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(urllib.request.Request(
                    base_url + "/wg/wifi/scan",
                    headers={
                        "Origin": "http://localhost:8000",
                        "X-WG-Token": original_token,
                    },
                ))
            self.assertEqual(error.exception.code, 403)

            connect_ping = urllib.request.urlopen(urllib.request.Request(
                base_url + "/wg/ping",
                headers={"Origin": "http://localhost:8000"},
            ))
            connect_token = connect_ping.headers["X-WG-Token"]
            connect_ping.read()
            with patch.object(wifi_server, "connect_wifi", return_value={"connected": True, "ssid": "Cafe"}) as connect:
                response = urllib.request.urlopen(urllib.request.Request(
                    base_url + "/wg/wifi/connect",
                    data=json.dumps({"ssid": "Cafe", "password": "not-logged"}).encode("utf-8"),
                    headers={
                        "Origin": "http://localhost:8000",
                        "Content-Type": "application/json",
                        "X-WG-Token": connect_token,
                    },
                    method="POST",
                ))
                self.assertEqual(json.loads(response.read()), {"connected": True, "ssid": "Cafe"})
                connect.assert_called_once_with("Cafe", "not-logged")
        finally:
            http_server.shutdown()
            http_server.server_close()
            thread.join(timeout=2)

    def test_file_origin_ping_is_allowed_by_default(self):
        http_server = WifiServer(("127.0.0.1", 0), WifiHandler, set())
        thread = threading.Thread(target=http_server.serve_forever, daemon=True)
        thread.start()
        try:
            response = urllib.request.urlopen(urllib.request.Request(
                "http://127.0.0.1:" + str(http_server.server_port) + "/wg/ping",
                headers={"Origin": "null"},
            ))
            self.assertEqual(response.headers["Access-Control-Allow-Origin"], "null")
            self.assertEqual(json.loads(response.read())["ok"], True)
        finally:
            http_server.shutdown()
            http_server.server_close()
            thread.join(timeout=2)

    def test_wifi_status_and_toggle_endpoints(self):
        http_server = WifiServer(("127.0.0.1", 0), WifiHandler, set())
        thread = threading.Thread(target=http_server.serve_forever, daemon=True)
        thread.start()
        base_url = "http://127.0.0.1:" + str(http_server.server_port)
        origin = "http://localhost:8000"
        try:
            ping = urllib.request.urlopen(urllib.request.Request(
                base_url + "/wg/ping",
                headers={"Origin": origin},
            ))
            token = ping.headers["X-WG-Token"]
            ping.read()

            status_data = {
                "available": True,
                "enabled": True,
                "interfaces": [{"description": "Wireless adapter", "state": "connected", "enabled": True}],
            }
            with patch.object(wifi_server, "get_wifi_status", return_value=status_data):
                status = urllib.request.urlopen(urllib.request.Request(
                    base_url + "/wg/wifi/status",
                    headers={"Origin": origin, "X-WG-Token": token},
                ))
                token = status.headers["X-WG-Token"]
                self.assertEqual(json.loads(status.read()), status_data)

            off_data = {
                "available": True,
                "enabled": False,
                "interfaces": [{"description": "Wireless adapter", "state": "disconnected", "enabled": False}],
            }
            with patch.object(wifi_server, "set_wifi_enabled", return_value=off_data) as toggle:
                response = urllib.request.urlopen(urllib.request.Request(
                    base_url + "/wg/wifi/toggle",
                    data=json.dumps({"enabled": False}).encode("utf-8"),
                    headers={
                        "Origin": origin,
                        "Content-Type": "application/json",
                        "X-WG-Token": token,
                    },
                    method="POST",
                ))
                self.assertEqual(json.loads(response.read()), off_data)
                toggle.assert_called_once_with(False)

            disconnect_ping = urllib.request.urlopen(urllib.request.Request(
                base_url + "/wg/ping",
                headers={"Origin": origin},
            ))
            token = disconnect_ping.headers["X-WG-Token"]
            disconnect_ping.read()
            with patch.object(
                wifi_server,
                "disconnect_wifi",
                return_value={"disconnected": True, "ssid": "Cafe"},
            ) as disconnect:
                response = urllib.request.urlopen(urllib.request.Request(
                    base_url + "/wg/wifi/disconnect",
                    data=json.dumps({"ssid": "Cafe"}).encode("utf-8"),
                    headers={
                        "Origin": origin,
                        "Content-Type": "application/json",
                        "X-WG-Token": token,
                    },
                    method="POST",
                ))
                self.assertEqual(
                    json.loads(response.read()),
                    {"disconnected": True, "ssid": "Cafe"},
                )
                disconnect.assert_called_once_with("Cafe")
        finally:
            http_server.shutdown()
            http_server.server_close()
            thread.join(timeout=2)

    def test_bluetooth_status_device_scan_pair_and_unpair_endpoints(self):
        http_server = WifiServer(("127.0.0.1", 0), WifiHandler, set())
        thread = threading.Thread(target=http_server.serve_forever, daemon=True)
        thread.start()
        base_url = "http://127.0.0.1:" + str(http_server.server_port)
        origin = "http://localhost:8000"
        device = {"address": "A1:B2:C3:D4:E5:F6", "name": "Headphones", "paired": True}
        try:
            ping = urllib.request.urlopen(urllib.request.Request(
                base_url + "/wg/ping",
                headers={"Origin": origin},
            ))
            token = ping.headers["X-WG-Token"]
            ping.read()

            def request(path, method="GET", body=None):
                nonlocal token
                headers = {"Origin": origin, "X-WG-Token": token}
                data = None
                if body is not None:
                    headers["Content-Type"] = "application/json"
                    data = json.dumps(body).encode("utf-8")
                response = urllib.request.urlopen(urllib.request.Request(
                    base_url + path,
                    data=data,
                    headers=headers,
                    method=method,
                ))
                token = response.headers["X-WG-Token"]
                return json.loads(response.read())

            status_data = {
                "available": True,
                "adapters": [{"name": "Bluetooth Radio", "address": "00:11:22:33:44:55"}],
            }
            with patch.object(wifi_server, "get_bluetooth_status", return_value=status_data):
                self.assertEqual(request("/wg/bluetooth/status"), status_data)

            with patch.object(wifi_server, "list_bluetooth_devices", return_value=[device]) as list_devices:
                self.assertEqual(request("/wg/bluetooth/devices"), {"devices": [device]})
                self.assertEqual(
                    request("/wg/bluetooth/scan"),
                    {"devices": [device]},
                )
                self.assertEqual(list_devices.call_args_list[0].args, ())
                self.assertEqual(list_devices.call_args_list[1].kwargs, {"scan": True})

            with patch.object(
                wifi_server,
                "pair_bluetooth_device",
                return_value={"paired": True, "address": device["address"]},
            ) as pair:
                self.assertEqual(
                    request("/wg/bluetooth/pair", "POST", {"address": device["address"]}),
                    {"paired": True, "address": device["address"]},
                )
                pair.assert_called_once_with(device["address"])

            with patch.object(
                wifi_server,
                "unpair_bluetooth_device",
                return_value={"removed": True, "address": device["address"]},
            ) as unpair:
                self.assertEqual(
                    request("/wg/bluetooth/unpair", "POST", {"address": device["address"]}),
                    {"removed": True, "address": device["address"]},
                )
                unpair.assert_called_once_with(device["address"])
        finally:
            http_server.shutdown()
            http_server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
