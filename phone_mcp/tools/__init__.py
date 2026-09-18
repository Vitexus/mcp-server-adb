"""
Tools module for Phone MCP.
Contains all the phone control functionality categorized by domain.
"""

# Import all submodules to make them accessible
from . import call
from . import messaging
from . import contacts
from . import media
from . import apps
from . import system

# Import new modules for extended functionality
from . import interactions
from . import ui
from . import ui_enhanced
from . import ui_monitor

from .call import call_number, end_call, receive_incoming_call, check_device_connection
from .messaging import send_text_message, receive_text_messages, get_sent_messages
from .media import take_screenshot, start_screen_recording, play_media
from .apps import (
    set_alarm,
    list_installed_apps,
    terminate_app,
    launch_app_activity,
    launch_intent,
    install_app,
    uninstall_app,
    grant_permission,
    open_file,
)
from .contacts import get_contacts, create_contact
from .system import (
    get_current_window,
    get_app_shortcuts,
    push_file,
    pull_file,
    get_screen_info,
)

# Basic interactions
from .interactions import tap_screen, swipe_screen, press_key, input_text, open_url

# Basic UI inspection
from .ui import dump_ui, find_element_by_text, find_element_by_id, tap_element

# Enhanced UI functionality
from .ui_enhanced import (
    find_element_by_content_desc,
    find_element_by_class,
    find_clickable_elements,
    wait_for_element,
    scroll_to_element,
)

# Import map-related functionality, including environment variable check
try:
    from .maps import get_phone_numbers_from_poi, HAS_VALID_API_KEY
except ImportError:
    # Define defaults if maps module can't be imported
    HAS_VALID_API_KEY = False
    
    async def get_phone_numbers_from_poi(*args, **kwargs):
        """Placeholder function when maps module is not available"""
        import json
        return json.dumps({"error": "Maps functionality not available. Module could not be imported."})

# Basic tools list
__all__ = [
    "call_number",
    "end_call",
    "receive_incoming_call",
    "check_device_connection",
    "send_text_message",
    "receive_text_messages",
    "get_sent_messages",
    "take_screenshot",
    "start_screen_recording",
    "play_media",
    "set_alarm",
    "list_installed_apps",
    "terminate_app",
    "get_contacts",
    "create_contact",
    "get_current_window",
    "get_app_shortcuts",
    "launch_app_activity",
    "launch_intent",
    "install_app",
    "uninstall_app",
    "grant_permission",
    "open_file",
    "push_file",
    "pull_file",
    "get_screen_info",
    "tap_screen",
    "swipe_screen",
    "press_key",
    "input_text",
    "open_url",
    "dump_ui",
    "find_element_by_text",
    "find_element_by_id",
    "tap_element",
    "find_element_by_content_desc",
    "find_element_by_class",
    "find_clickable_elements",
    "wait_for_element",
    "scroll_to_element",
]

# Only add map functionality if there is a valid API key
if HAS_VALID_API_KEY:
    __all__.append("get_phone_numbers_from_poi")
