import argparse
import asyncio
from fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("phone_call")

# Import all tools
from .core import check_device_connection
from .tools.call import call_number, end_call, receive_incoming_call
from .tools.messaging import send_text_message, receive_text_messages, get_sent_messages
from .tools.media import take_screenshot, start_screen_recording, play_media
from .tools.apps import (
    set_alarm,
    list_installed_apps,
    terminate_app,
    launch_app_activity,
    install_app,
    uninstall_app,
    grant_permission,
    open_file,
)
from .tools.contacts import get_contacts, create_contact
from .tools.system import (
    get_current_window,
    get_app_shortcuts,
    push_file,
    pull_file,
    get_screen_info,
)
# Import screen interface for unified interaction and analysis
from .tools.screen_interface import analyze_screen, interact_with_screen
# Import UI monitoring - use MCP compatible version
from .tools.ui_monitor import mcp_monitor_ui_changes
from .tools.interactions import open_url

# Import map functionality if available
try:
    from .tools.maps import get_phone_numbers_from_poi, HAS_VALID_API_KEY
except ImportError:
    HAS_VALID_API_KEY = False

# Register all tools with MCP
mcp.tool()(call_number)
mcp.tool()(end_call)
mcp.tool()(check_device_connection)
mcp.tool()(send_text_message)
mcp.tool()(receive_text_messages)
mcp.tool()(get_sent_messages)
# mcp.tool()(take_screenshot)
mcp.tool()(start_screen_recording)
mcp.tool()(play_media)
mcp.tool()(set_alarm)
mcp.tool()(receive_incoming_call)
mcp.tool()(get_contacts)
mcp.tool()(create_contact)
mcp.tool()(get_current_window)
mcp.tool()(get_app_shortcuts)
mcp.tool()(launch_app_activity)
mcp.tool()(list_installed_apps)
mcp.tool()(terminate_app)
mcp.tool()(install_app)
mcp.tool()(uninstall_app)
mcp.tool()(grant_permission)
mcp.tool()(open_file)
mcp.tool()(push_file)
mcp.tool()(pull_file)
mcp.tool()(get_screen_info)
mcp.tool()(open_url)

# Register unified screen interface tools
mcp.tool()(analyze_screen)
mcp.tool()(interact_with_screen)
mcp.tool()(mcp_monitor_ui_changes)

# Conditionally register map tool if API key is available
if HAS_VALID_API_KEY:
    mcp.tool()(get_phone_numbers_from_poi)


def main():
    """Run the MCP server."""
    parser = argparse.ArgumentParser(
        prog="phone-mcp",
        description=(
            "Model Context Protocol server for controlling Android phones "
            "via ADB. Intended to be launched by an MCP client and spoken "
            "to over stdio; takes no arguments during normal operation."
        ),
    )
    parser.parse_args()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    # Initialize and run the server
    main()
