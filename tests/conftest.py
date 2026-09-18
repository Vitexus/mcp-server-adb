import os
import sys
import pytest
import asyncio
import warnings
from pathlib import Path
from unittest.mock import patch

# Prefer the in-tree package over any system-installed phone_mcp
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Allow mutating tools (call/SMS/etc.) during unit tests; production defaults to read-only.
os.environ.setdefault("PHONE_READONLY", "false")

# 不使用pytest_plugins，而是直接配置插件
# pytest_plugins = ['pytest_asyncio']


# 定义全局pytest配置
def pytest_configure(config):
    """配置pytest运行时环境"""
    # 添加自定义标记
    config.addinivalue_line("markers", "amap: 标记高德地图API相关的测试")
    config.addinivalue_line("markers", "device: 标记设备连接相关的测试")
    config.addinivalue_line("markers", "cli: 标记CLI命令相关的测试")
    config.addinivalue_line("markers", "asyncio: 标记异步测试用例")


# 清理环境变量的自动fixture
@pytest.fixture(autouse=True)
def clean_env():
    """每次测试前清理可能影响测试的环境变量"""
    # 保存原始环境变量
    saved_vars = {}
    test_vars = ["AMAP_MAPS_API_KEY"]

    for var in test_vars:
        if var in os.environ:
            saved_vars[var] = os.environ[var]
            del os.environ[var]

    yield

    # 恢复原始环境变量
    for var, value in saved_vars.items():
        os.environ[var] = value


# 忽略asyncio警告的fixture
@pytest.fixture(autouse=True)
def ignore_asyncio_warnings():
    """忽略asyncio相关的运行时警告"""
    # 过滤掉asyncio相关的警告
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="asyncio")
    # 这个函数不再使用pytest.warns，这样不会期望警告
    yield
    # 重置警告过滤器
    warnings.resetwarnings()


# 提供模拟的app实例
@pytest.fixture
def mock_app():
    """提供模拟的app对象，用于CLI测试"""

    class MockApp:
        def __init__(self):
            self.args = None
            self.command_called = None

        async def call_command(self, command, args):
            self.command_called = command
            self.args = args
            return f"Called {command} with {args}"

    return MockApp()


# 模拟整个命令行界面运行
@pytest.fixture
def mock_cli_run():
    """模拟CLI运行，捕获参数和命令"""
    with patch("sys.argv") as mock_argv:
        with patch("asyncio.run") as mock_run:
            yield mock_argv, mock_run
