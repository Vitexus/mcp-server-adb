import os
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from phone_mcp.tools.maps import get_phone_numbers_from_poi, HAS_VALID_API_KEY
import phone_mcp


@pytest.fixture
def amap_key():
    """Provide a temporary AMap API key via environment."""
    original_key = os.environ.get("AMAP_MAPS_API_KEY")
    os.environ["AMAP_MAPS_API_KEY"] = "test_api_key"
    yield "test_api_key"
    if original_key:
        os.environ["AMAP_MAPS_API_KEY"] = original_key
    else:
        os.environ.pop("AMAP_MAPS_API_KEY", None)


@pytest.mark.amap
class TestPOISearch:
    """Tests for AMap POI phone-number lookup."""

    @pytest.mark.usefixtures("amap_key")
    def test_api_key_env_variable(self):
        import importlib

        importlib.reload(phone_mcp.tools.maps)
        from phone_mcp.tools.maps import HAS_VALID_API_KEY as has_key

        assert has_key is True

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("amap_key")
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
                        "location": "116.310905,39.992806",
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
            result = await get_poi("116.310905,39.992806", "餐厅", "1000")

        result_data = json.loads(result)
        assert "pois" in result_data
        assert "测试餐厅" in result

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("amap_key")
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
            result = await get_poi("116.310905,39.992806", "餐厅")

        result_data = json.loads(result)
        assert "error" in result_data
        assert "POI search failed" in result_data["error"]

    @pytest.mark.asyncio
    async def test_get_phone_numbers_from_poi_no_api_key(self):
        os.environ.pop("AMAP_MAPS_API_KEY", None)
        import importlib

        importlib.reload(phone_mcp.tools.maps)
        from phone_mcp.tools.maps import get_phone_numbers_from_poi as get_poi

        result = await get_poi("116.310905,39.992806")
        result_data = json.loads(result)
        assert "error" in result_data
        assert "API key not configured" in result_data["error"]

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("amap_key")
    async def test_get_phone_numbers_from_poi_request_exception(self):
        import importlib

        importlib.reload(phone_mcp.tools.maps)
        from phone_mcp.tools.maps import get_phone_numbers_from_poi as get_poi

        with patch(
            "aiohttp.ClientSession",
            side_effect=Exception("Connection error"),
        ):
            result = await get_poi("116.310905,39.992806")

        result_data = json.loads(result)
        assert "error" in result_data
        assert "Request failed" in result_data["error"]
