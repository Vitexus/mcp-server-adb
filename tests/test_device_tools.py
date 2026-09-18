"""Tests for app install/uninstall, permissions, file transfer and screen info."""

import json
import pytest
from unittest.mock import AsyncMock, patch

from phone_mcp.tools.apps import (
    install_app,
    uninstall_app,
    grant_permission,
    open_file,
)
from phone_mcp.tools.system import push_file, pull_file, get_screen_info


@pytest.fixture(autouse=True)
def writable(monkeypatch):
    """Take the server out of its fail-closed read-only default."""
    monkeypatch.setenv("PHONE_READONLY", "false")


@pytest.fixture
def apps_adb():
    """Mock the device check and adb calls made by phone_mcp.tools.apps."""
    with patch(
        "phone_mcp.tools.apps.check_device_connection",
        new=AsyncMock(return_value="Device is connected and ready."),
    ), patch(
        "phone_mcp.tools.apps.run_command", new_callable=AsyncMock
    ) as mock_run:
        yield mock_run


@pytest.fixture
def system_adb():
    """Mock the device check and adb calls made by phone_mcp.tools.system."""
    with patch(
        "phone_mcp.tools.system.check_device_connection",
        new=AsyncMock(return_value="Device is connected and ready."),
    ), patch(
        "phone_mcp.tools.system.run_command", new_callable=AsyncMock
    ) as mock_run:
        yield mock_run


@pytest.mark.asyncio
class TestInstallApp:
    async def test_install_success(self, apps_adb, tmp_path):
        apk = tmp_path / "app.apk"
        apk.write_bytes(b"not really an apk")
        apps_adb.side_effect = [
            (True, "Performing Streamed Install\nSuccess\n"),
            (False, "aapt: not found"),
            (False, "aapt2: not found"),
        ]

        result = json.loads(await install_app(str(apk)))

        assert result["status"] == "success"
        assert "package_name" not in result
        assert " -r " in apps_adb.call_args_list[0][0][0]

    async def test_install_reports_package_name(self, apps_adb, tmp_path):
        apk = tmp_path / "app.apk"
        apk.write_bytes(b"not really an apk")
        apps_adb.side_effect = [
            (True, "Success\n"),
            (True, "package: name='com.example.app' versionCode='7'"),
        ]

        result = json.loads(await install_app(str(apk)))

        assert result["package_name"] == "com.example.app"

    async def test_install_missing_apk(self, apps_adb, tmp_path):
        result = json.loads(await install_app(str(tmp_path / "gone.apk")))

        assert result["status"] == "error"
        assert "not found" in result["message"]
        apps_adb.assert_not_called()

    async def test_install_failure_is_read_from_output(self, apps_adb, tmp_path):
        # adb prints its verdict on stdout, so a failure can arrive as success
        apk = tmp_path / "app.apk"
        apk.write_bytes(b"not really an apk")
        apps_adb.return_value = (True, "Failure [INSTALL_FAILED_INVALID_APK]")

        result = json.loads(await install_app(str(apk)))

        assert result["status"] == "error"
        assert "INSTALL_FAILED_INVALID_APK" in result["message"]

    async def test_install_blocked_in_read_only_mode(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PHONE_READONLY", "true")
        apk = tmp_path / "app.apk"
        apk.write_bytes(b"not really an apk")

        result = json.loads(await install_app(str(apk)))

        assert result["status"] == "error"
        assert "read-only" in result["message"]


@pytest.mark.asyncio
class TestUninstallApp:
    async def test_uninstall_success(self, apps_adb):
        apps_adb.return_value = (True, "Success\n")

        result = json.loads(await uninstall_app("com.example.app"))

        assert result["status"] == "success"

    async def test_uninstall_keep_data_flag(self, apps_adb):
        apps_adb.return_value = (True, "Success\n")

        await uninstall_app("com.example.app", keep_data=True)

        assert " -k " in apps_adb.call_args[0][0]

    async def test_uninstall_failure(self, apps_adb):
        apps_adb.return_value = (True, "Failure [DELETE_FAILED_INTERNAL_ERROR]")

        result = json.loads(await uninstall_app("com.example.missing"))

        assert result["status"] == "error"
        assert "DELETE_FAILED_INTERNAL_ERROR" in result["message"]


@pytest.mark.asyncio
class TestGrantPermission:
    async def test_runtime_permission_uses_pm_grant(self, apps_adb):
        apps_adb.return_value = (True, "")

        result = json.loads(
            await grant_permission(
                "com.example.app", "android.permission.READ_EXTERNAL_STORAGE"
            )
        )

        assert result["status"] == "success"
        assert "pm grant" in apps_adb.call_args[0][0]

    async def test_bare_permission_name_is_qualified(self, apps_adb):
        apps_adb.return_value = (True, "")

        await grant_permission("com.example.app", "CAMERA")

        assert "android.permission.CAMERA" in apps_adb.call_args[0][0]

    async def test_special_permission_uses_appops(self, apps_adb):
        apps_adb.return_value = (True, "")

        await grant_permission(
            "com.example.app", "android.permission.MANAGE_EXTERNAL_STORAGE"
        )

        cmd = apps_adb.call_args[0][0]
        assert "appops set" in cmd
        assert "MANAGE_EXTERNAL_STORAGE allow" in cmd
        assert "pm grant" not in cmd

    async def test_failure_keeps_only_the_first_line(self, apps_adb):
        apps_adb.return_value = (
            False,
            "Exception occurred while executing 'grant':\n\tat com.android.server",
        )

        result = json.loads(
            await grant_permission("com.example.app", "android.permission.NOPE")
        )

        assert result["status"] == "error"
        assert "at com.android.server" not in result["message"]


@pytest.mark.asyncio
class TestOpenFile:
    async def test_open_with_component_and_mime(self, apps_adb):
        apps_adb.side_effect = [
            (True, "/sdcard/Download/book.epub"),
            (True, "Starting: Intent { ... }"),
        ]

        result = json.loads(
            await open_file(
                "/sdcard/Download/book.epub",
                "com.example.reader",
                ".ViewerActivity",
                "application/epub+zip",
            )
        )

        assert result["status"] == "success"
        cmd = apps_adb.call_args[0][0]
        assert "android.intent.action.VIEW" in cmd
        assert "file:///sdcard/Download/book.epub" in cmd
        assert "application/epub+zip" in cmd
        assert "com.example.reader/.ViewerActivity" in cmd

    async def test_open_without_app_omits_component(self, apps_adb):
        apps_adb.side_effect = [
            (True, "/sdcard/Download/book.epub"),
            (True, "Starting: Intent { ... }"),
        ]

        await open_file("/sdcard/Download/book.epub")

        assert " -n " not in apps_adb.call_args[0][0]

    async def test_missing_file_on_device(self, apps_adb):
        apps_adb.return_value = (False, "ls: /sdcard/gone.pdf: No such file")

        result = json.loads(await open_file("/sdcard/gone.pdf"))

        assert result["status"] == "error"
        assert "not found on device" in result["message"]

    async def test_am_start_error_on_stdout_is_a_failure(self, apps_adb):
        apps_adb.side_effect = [
            (True, "/sdcard/Download/book.epub"),
            (True, "Error: Activity class does not exist."),
        ]

        result = json.loads(
            await open_file("/sdcard/Download/book.epub", "com.example.reader", ".Gone")
        )

        assert result["status"] == "error"


@pytest.mark.asyncio
class TestFileTransfer:
    async def test_push_to_directory_reports_full_path(self, system_adb, tmp_path):
        local = tmp_path / "book.epub"
        local.write_bytes(b"epub bytes")
        system_adb.return_value = (True, "1 file pushed")

        result = json.loads(await push_file(str(local), "/sdcard/Download/"))

        assert result["status"] == "success"
        assert result["device_path"] == "/sdcard/Download/book.epub"
        assert result["size_bytes"] == len(b"epub bytes")

    async def test_push_missing_local_file(self, system_adb, tmp_path):
        result = json.loads(await push_file(str(tmp_path / "gone"), "/sdcard/"))

        assert result["status"] == "error"
        system_adb.assert_not_called()

    async def test_pull_success(self, system_adb, tmp_path):
        target = tmp_path / "pulled.epub"

        async def fake_pull(cmd, timeout=None):
            target.write_bytes(b"epub bytes")
            return True, "1 file pulled"

        system_adb.side_effect = fake_pull

        result = json.loads(await pull_file("/sdcard/book.epub", str(target)))

        assert result["status"] == "success"
        assert result["local_path"] == str(target)
        assert result["size_bytes"] == len(b"epub bytes")

    async def test_pull_reports_missing_target(self, system_adb, tmp_path):
        system_adb.return_value = (True, "1 file pulled")

        result = json.loads(
            await pull_file("/sdcard/book.epub", str(tmp_path / "nothing.epub"))
        )

        assert result["status"] == "error"
        assert "missing" in result["message"]


@pytest.mark.asyncio
class TestScreenInfo:
    async def test_parses_size_density_and_rotation(self, system_adb):
        system_adb.side_effect = [
            (True, "Physical size: 1080x2340\n"),
            (True, "Physical density: 480\n"),
            (
                True,
                "  Display: mDisplayId=0\n"
                "    init=1080x2340 480dpi cur=2340x1080 app=2340x1080\n"
                "    mCurrentRotation=ROTATION_90\n",
            ),
        ]

        result = json.loads(await get_screen_info())

        assert result["physical_size"] == {"width": 1080, "height": 2340}
        assert result["current_size"] == {"width": 2340, "height": 1080}
        assert result["density_dpi"] == 480
        assert result["rotation_degrees"] == 90
        assert result["orientation"] == "landscape"

    async def test_override_size_is_reported(self, system_adb):
        system_adb.side_effect = [
            (True, "Physical size: 1080x2340\nOverride size: 720x1560\n"),
            (True, "Physical density: 320\n"),
            (True, ""),
        ]

        result = json.loads(await get_screen_info())

        assert result["override_size"] == {"width": 720, "height": 1560}
        # with no display dump the physical size decides the orientation
        assert result["orientation"] == "portrait"

    async def test_size_command_failure(self, system_adb):
        system_adb.return_value = (False, "device offline")

        result = json.loads(await get_screen_info())

        assert result["status"] == "error"
