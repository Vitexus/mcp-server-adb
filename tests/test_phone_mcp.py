import os
import json
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import phone_mcp
from phone_mcp.core import check_device_connection, run_command
from phone_mcp.tools.maps import get_phone_numbers_from_poi, HAS_VALID_API_KEY


@pytest.fixture
def adb_mock():
    """Mock ADB command execution."""
    with patch("phone_mcp.core.run_command", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def api_key_env():
    """Set AMap API key for the duration of the test."""
    old_key = os.environ.get("AMAP_MAPS_API_KEY")
    os.environ["AMAP_MAPS_API_KEY"] = "test_api_key"
    yield
    if old_key:
        os.environ["AMAP_MAPS_API_KEY"] = old_key
    else:
        os.environ.pop("AMAP_MAPS_API_KEY", None)


@pytest.mark.asyncio
class TestDeviceConnection:
    async def test_check_device_connection_connected(self, adb_mock):
        adb_mock.return_value = (True, "List of devices attached\nXXXXXXXX\tdevice")
        result = await check_device_connection()
        assert "connected and ready" in result
        adb_mock.assert_called_with("adb devices")

    async def test_check_device_connection_not_connected(self, adb_mock):
        adb_mock.return_value = (True, "List of devices attached\n")
        result = await check_device_connection()
        assert "No device found" in result


@pytest.mark.amap
class TestMapAPI:
    @pytest.mark.usefixtures("api_key_env")
    def test_api_key_env_variable(self):
        import importlib

        importlib.reload(phone_mcp.tools.maps)
        from phone_mcp.tools.maps import HAS_VALID_API_KEY as has_key

        assert has_key is True

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("api_key_env")
    async def test_get_phone_numbers_from_poi_success(self):
        import importlib

        importlib.reload(phone_mcp.tools.maps)
        from phone_mcp.tools.maps import get_phone_numbers_from_poi as get_poi

        mock_response = MagicMock()
        mock_response.json = AsyncMock(
            return_value={
                "status": "1",
                "pois": [
                    {
                        "name": "测试餐厅",
                        "address": "测试地址",
                        "tel": "12345678901",
                        "location": "116.480053,39.987005",
                    }
                ],
            }
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await get_poi("116.480053,39.987005", "餐厅", "1000")

        result_data = json.loads(result)
        assert "测试餐厅" in result
        assert "pois" in result_data

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("api_key_env")
    async def test_get_phone_numbers_from_poi_api_error(self):
        import importlib

        importlib.reload(phone_mcp.tools.maps)
        from phone_mcp.tools.maps import get_phone_numbers_from_poi as get_poi

        mock_response = MagicMock()
        mock_response.json = AsyncMock(
            return_value={"status": "0", "info": "INVALID_KEY"}
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await get_poi("116.480053,39.987005", "餐厅")

        result_data = json.loads(result)
        assert "error" in result_data
        assert "POI search failed" in result_data["error"]

    @pytest.mark.asyncio
    async def test_get_phone_numbers_from_poi_no_api_key(self):
        os.environ.pop("AMAP_MAPS_API_KEY", None)
        import importlib

        importlib.reload(phone_mcp.tools.maps)
        from phone_mcp.tools.maps import get_phone_numbers_from_poi as get_poi

        result = await get_poi("116.480053,39.987005")
        result_data = json.loads(result)
        assert "error" in result_data
        assert "API key not configured" in result_data["error"]


class TestCLICommands:
    def test_cli_commands_availability(self):
        from phone_mcp import cli
        import inspect

        source = inspect.getsource(cli)
        assert "check" in source
        assert "screenshot" in source
        assert "contacts" in source
        assert "HAS_VALID_API_KEY" in source
        assert "get-poi" in source
