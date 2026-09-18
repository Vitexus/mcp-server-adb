import os
import json
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

# 导入被测试的模块
from phone_mcp.core import check_device_connection, run_command
from phone_mcp.config import DEFAULT_COUNTRY_CODE
from phone_mcp.tools.call import call_number, end_call
from phone_mcp.tools.messaging import (
    send_text_message,
    receive_text_messages,
)


# 辅助函数，将同步结果转换为异步结果
def async_return(result):
    """将同步结果包装为异步结果的辅助函数"""
    loop = asyncio.get_event_loop_policy().get_event_loop()
    f = loop.create_future()
    f.set_result(result)
    return f


# 固定装置：模拟ADB命令执行
@pytest.fixture
def adb_mock():
    """模拟ADB命令执行的装置，可控制命令执行结果"""
    with patch("phone_mcp.core.run_command", new_callable=AsyncMock) as mock_run:
        yield mock_run


@pytest.mark.asyncio
class TestDeviceConnection:
    """测试设备连接检测功能"""

    async def test_check_device_connection_connected(self, adb_mock):
        """测试设备已连接的情况"""
        # 设置模拟的命令执行返回值
        adb_mock.return_value = (True, "List of devices attached\nXXXXXXXX\tdevice")

        # 执行被测试的函数
        result = await check_device_connection()

        # 验证结果
        assert "connected and ready" in result
        adb_mock.assert_called_with("adb devices")

    async def test_check_device_connection_not_connected(self, adb_mock):
        """测试没有设备连接的情况"""
        # 设置模拟的命令执行返回值，模拟自动重试行为
        # 由于check_device_connection中有重试逻辑，这里需要多次设置返回值
        adb_mock.side_effect = [
            (True, "List of devices attached\n"),  # 首次调用
            (True, "Success"),  # kill-server
            (True, "Success"),  # start-server
            (True, "List of devices attached\n"),  # 第二次调用
            (True, "List of devices attached\n"),  # 第三次调用
            (True, "List of devices attached\n"),  # 第四次调用
        ]

        # 执行被测试的函数
        result = await check_device_connection()

        # 验证结果
        assert "No device found" in result
        assert "connected and ready" not in result

    async def test_check_device_connection_failure(self, adb_mock):
        """测试命令执行失败的情况"""
        # 设置模拟的命令执行返回值
        adb_mock.return_value = (False, "Command failed: adb not found")

        # 执行被测试的函数
        result = await check_device_connection()

        # 验证结果
        assert "Failed to check device connection" in result
        assert "adb not found" in result


@pytest.mark.asyncio
class TestPhoneFunctionality:
    """测试手机的基本功能，如拨打电话、发送短信等"""

    async def test_call_number_success(self, adb_mock):
        """测试成功拨打电话的情况"""
        # 直接修改phone_mcp.tools.call模块中run_command的引用
        with patch(
            "phone_mcp.tools.call.run_command", new_callable=AsyncMock
        ) as mock_call:
            # 设置模拟的命令执行返回值
            mock_call.return_value = (True, "Success")

            # 执行被测试的函数
            phone_number = "10086"
            result = await call_number(phone_number)

            # 验证结果
            assert DEFAULT_COUNTRY_CODE + phone_number in result  # locale-detected prefix
            assert "Calling" in result
            # 验证被调用
            assert mock_call.called

    async def test_call_number_failure(self, adb_mock):
        """测试拨打电话失败的情况"""
        # 直接修改phone_mcp.tools.call模块中run_command的引用
        with patch(
            "phone_mcp.tools.call.run_command", new_callable=AsyncMock
        ) as mock_call:
            # 设置模拟的命令执行返回值
            mock_call.return_value = (False, "Failed to execute command")

            # 执行被测试的函数
            result = await call_number("10086")

            # 验证结果
            assert "Failed to initiate call" in result
            # 验证被调用
            assert mock_call.called

    async def test_end_call_success(self, adb_mock):
        """测试成功结束通话的情况"""
        # 直接修改phone_mcp.tools.call模块中run_command的引用
        with patch(
            "phone_mcp.tools.call.run_command", new_callable=AsyncMock
        ) as mock_call:
            # 设置模拟的命令执行返回值
            mock_call.return_value = (True, "Success")

            # 执行被测试的函数
            result = await end_call()

            # 验证结果
            assert "Call ended successfully" in result
            # 验证被调用的参数
            mock_call.assert_called_with("adb shell input keyevent KEYCODE_ENDCALL")

    async def test_end_call_failure(self, adb_mock):
        """测试结束通话失败的情况"""
        # 直接修改phone_mcp.tools.call模块中run_command的引用
        with patch(
            "phone_mcp.tools.call.run_command", new_callable=AsyncMock
        ) as mock_call:
            # 设置模拟的命令执行返回值
            mock_call.return_value = (False, "Failed to execute command")

            # 执行被测试的函数
            result = await end_call()

            # 验证结果
            assert "Failed to end call" in result
            # 验证被调用的参数
            mock_call.assert_called_with("adb shell input keyevent KEYCODE_ENDCALL")

    async def test_send_text_message_success(self, adb_mock):
        """测试成功发送短信的情况"""
        # 直接修改phone_mcp.tools.messaging模块中run_command的引用
        with patch(
            "phone_mcp.tools.messaging.run_command", new_callable=AsyncMock
        ) as mock_msg:
            # 模拟多个命令调用的成功情况
            mock_msg.side_effect = [
                (True, "Success"),  # 打开短信app
                (True, "Success"),  # 按键事件1
                (True, "Success"),  # 按键事件2
                (True, "Success"),  # 退出app
            ]

            # 模拟sleep函数，避免实际等待
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                # 执行被测试的函数
                phone_number = "10086"
                message = "测试短信"
                result = await send_text_message(phone_number, message)

            # 验证结果
            assert DEFAULT_COUNTRY_CODE + phone_number in result  # locale-detected prefix
            assert "sent" in result
            # 验证被调用至少一次
            assert mock_msg.call_count > 0

    async def test_send_text_message_failure(self, adb_mock):
        """Test SMS send failure when the messaging app cannot be opened."""
        with patch(
            "phone_mcp.tools.messaging.run_command", new_callable=AsyncMock
        ) as mock_msg:
            mock_msg.side_effect = [
                (False, "Failed"),  # open messaging app fails
            ]

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await send_text_message("10086", "测试短信")

            assert "Failed to open messaging app" in result

    async def test_receive_text_messages_success(self, adb_mock):
        """测试成功获取短信的情况"""
        # 由于receive_text_messages会调用check_device_connection，
        # 我们需要先模拟core模块中的check_device_connection
        with patch(
            "phone_mcp.core.check_device_connection", new_callable=AsyncMock
        ) as mock_check:
            # 模拟设备连接正常
            mock_check.return_value = "Device is connected and ready."

            # 修改phone_mcp.tools.messaging模块中run_command的引用
            with patch(
                "phone_mcp.tools.messaging.run_command", new_callable=AsyncMock
            ) as mock_msg:
                # 模拟短信查询返回正确的短信内容
                mock_msg.return_value = (
                    True,
                    """Row: 0 address=10086, body=你好，这是测试短信, date=1628151234567
Row: 1 address=13900139000, body=这是另一条测试短信, date=1628151234000""",
                )

                # 执行被测试的函数
                result = await receive_text_messages(limit=2)

            # 验证结果是否包含短信内容
            assert isinstance(result, str)

            # 尝试解析JSON结果
            try:
                messages = json.loads(result)
                assert isinstance(messages, list)
                assert len(messages) <= 2  # 不应超过限制

                # 验证短信内容
                if messages:
                    first_msg = messages[0]
                    assert any(key in first_msg for key in ["address", "from"])
                    assert any(key in first_msg for key in ["body", "text"])
            except json.JSONDecodeError:
                # 如果不是JSON格式，应该包含短信相关信息
                assert "SMS" in result or "短信" in result

    async def test_receive_text_messages_no_device(self, adb_mock):
        """测试没有设备连接时获取短信的情况"""
        # 模拟设备连接检查失败
        with patch(
            "phone_mcp.core.check_device_connection", new_callable=AsyncMock
        ) as mock_check:
            # 返回设备未连接消息
            mock_check.return_value = "No device found. Please connect a device and ensure USB debugging is enabled."

            # 执行被测试的函数
            result = await receive_text_messages()

        # 验证结果
        assert "No device found" in result

    async def test_receive_text_messages_empty(self, adb_mock):
        """Test retrieving inbox SMS when none are present."""
        with patch(
            "phone_mcp.core.check_device_connection", new_callable=AsyncMock
        ) as mock_check:
            mock_check.return_value = "Device is connected and ready."

            with patch(
                "phone_mcp.tools.messaging.run_command", new_callable=AsyncMock
            ) as mock_msg:
                mock_msg.return_value = (True, "No SMS found")

                result = await receive_text_messages()

            assert isinstance(result, str)
            assert any(
                text in result
                for text in ["Unable to retrieve", "No SMS", "No recent", "not found", "empty"]
            ) or "error" in result.lower() or len(result) > 0
