"""
System-related functions for Phone MCP.
This module provides functions to access system-level information on the phone.
"""

import asyncio
import json
import os
import re
import shlex
from ..core import run_command, check_device_connection
from ..readonly import require_writable


async def get_current_window():
    """Get information about the current active window on the device.

    Retrieves details about the currently focused window, active application,
    and foreground activities on the device using multiple methods for reliability.

    Returns:
        str: JSON string with current window details or error message
    """
    # Check for connected device
    from ..core import check_device_connection

    connection_status = await check_device_connection()
    if "ready" not in connection_status:
        return connection_status

    try:
        window_info = {}
        success_count = 0

        # Method 1: Get current focus information (most reliable)
        cmd = "adb shell dumpsys window windows"
        success, output = await run_command(cmd)

        if success and output.strip():
            success_count += 1
            # Process the output with Python instead of grep
            focus_patterns = ["mCurrentFocus", "mFocusedApp"]

            for line in output.strip().split("\n"):
                line = line.strip()
                if any(pattern in line for pattern in focus_patterns):
                    if "mCurrentFocus" in line:
                        window_info["current_focus"] = line.replace(
                            "mCurrentFocus=", ""
                        ).strip()

                        # Extract package and activity
                        match = re.search(r"(\S+)/(\S+)", line)
                        if match:
                            window_info["package_name"] = match.group(1)
                            window_info["activity_name"] = match.group(2)
                    elif "mFocusedApp" in line:
                        window_info["focused_app"] = line.replace(
                            "mFocusedApp=", ""
                        ).strip()

        # Method 2: Get current resumed activity
        cmd = "adb shell dumpsys activity activities"
        success, output = await run_command(cmd)

        if success and output.strip():
            # Use Python to find resumed activities
            activity_patterns = ["ResumedActivity", "mResumedActivity"]

            for line in output.strip().split("\n"):
                if any(pattern in line for pattern in activity_patterns):
                    window_info["resumed_activity"] = line.strip()
                    success_count += 1
                    break

        # Method 3: Get top activity using am command
        cmd = "adb shell am stack list"
        success, output = await run_command(cmd)

        if not success or "Error" in output:
            # Newer Android versions use different command
            cmd = "adb shell cmd activity activities"
            success, output = await run_command(cmd)

            if success and output.strip():
                # Python processing for activity/topResumedActivity
                filtered_lines = []
                for line in output.strip().split("\n"):
                    if "ACTIVITY" in line or "topResumedActivity" in line:
                        filtered_lines.append(line.strip())

                if filtered_lines:
                    output = "\n".join(filtered_lines)

        if success and output.strip():
            success_count += 1
            window_info["activity_stack"] = output.strip().split("\n")[0:2]

            # Try to extract the package name if we don't have it yet
            if "package_name" not in window_info:
                package_match = re.search(r"([a-zA-Z0-9_.]+)/[a-zA-Z0-9_.]+", output)
                if package_match:
                    window_info["package_name"] = package_match.group(1)

        # Method 4: Get recent apps info
        cmd = "adb shell dumpsys activity recents"
        success, output = await run_command(cmd)

        if success and output.strip():
            # Use Python to find Recent #0 line
            for line in output.strip().split("\n"):
                if "Recent #0" in line:
                    window_info["recent_activity"] = line.strip()
                    success_count += 1
                    break

        # If we still don't have package info, try direct method
        if "package_name" not in window_info:
            cmd = "adb shell dumpsys window"
            success, output = await run_command(cmd)
            if success and output.strip():
                # Python processing for mCurrentFocus
                for line in output.strip().split("\n"):
                    if "mCurrentFocus" in line:
                        match = re.search(r"([a-zA-Z0-9_.]+)/[a-zA-Z0-9_.]+", line)
                        if match:
                            window_info["package_name"] = match.group(1)
                        break

        # Add device screen state
        cmd = "adb shell dumpsys power"
        success, output = await run_command(cmd)
        if success and output.strip():
            # Python processing for power state
            screen_state_patterns = ["mWakefulness=", "Display Power"]
            for line in output.strip().split("\n"):
                if any(pattern in line for pattern in screen_state_patterns):
                    window_info["screen_state"] = (
                        "on" if "ON" in line or "AWAKE" in line else "off"
                    )
                    break

        if success_count > 0:
            return json.dumps(window_info, indent=2)
        else:
            # Last resort - just get basic device info
            cmd = "adb shell getprop ro.product.model"
            success, model = await run_command(cmd)
            if success:
                return json.dumps(
                    {
                        "basic_info": "Unable to get window details",
                        "device_model": model.strip(),
                    },
                    indent=2,
                )
            else:
                return "Failed to retrieve current window information"
    except Exception as e:
        return f"Error retrieving window information: {str(e)}"


async def launch_app_activity(package_component=None, action=None, extra_args=None):
    """Launch an app by starting a specific activity with custom action and component.

    This function starts an application by launching a specific activity component.
    It effectively launches the app and can be used in conjunction with get_app_shortcuts 
    to discover available activities, but does not require it as a prerequisite.

    Args:
        package_component (str): App component in format "package/activity" (e.g. "com.example.app/.MainActivity")
                               This is the primary way to specify which app and activity to launch
        action (str, optional): Intent action to use (e.g. "android.intent.action.VIEW")
        extra_args (str, optional): Additional intent arguments to pass (e.g. "-d 'content://contacts/people/'")

    Returns:
        str: Success message with the launched component name, or error details if launch failed

    Example:
        To launch the main activity of an app:
        launch_app_activity("com.example.app/.MainActivity")
        
        To launch a specific activity with an action and data:
        launch_app_activity("com.android.browser/.BrowserActivity", 
                         action="android.intent.action.VIEW", 
                         extra_args="-d 'https://example.com'")
    """
    # Check for connected device
    from ..core import check_device_connection

    connection_status = await check_device_connection()
    if "ready" not in connection_status:
        return connection_status

    try:
        cmd_parts = ["adb shell am start"]

        # Add action if provided
        if action:
            cmd_parts.append(f'-a "{action}"')

        # Add component if provided
        if package_component:
            cmd_parts.append(f'-n "{package_component}"')

        # Add any extra arguments
        if extra_args:
            cmd_parts.append(extra_args)

        # Combine into final command
        cmd = " ".join(cmd_parts)

        # Execute the command
        success, output = await run_command(cmd)

        if success and ("Starting" in output or "Activity" in output):
            component = package_component or "specified activity"
            return f"Successfully launched {component}"
        else:
            return f"Failed to launch activity: {output}"
    except Exception as e:
        return f"Error launching activity: {str(e)}"


async def get_app_shortcuts(package_name=None):
    """Get application shortcuts for installed apps.

    Retrieves shortcuts (quick actions) available for Android apps.
    If package_name is provided, returns shortcuts only for that app,
    otherwise lists all apps with shortcuts.

    Args:
        package_name (str, optional): Specific app package to get shortcuts for

    Returns:
        str: JSON string with app shortcuts information or error message
    """
    # Check for connected device
    from ..core import check_device_connection

    connection_status = await check_device_connection()
    if "ready" not in connection_status:
        return connection_status

    try:
        # Use direct dumpsys shortcut command - most reliable method
        cmd = "adb shell dumpsys shortcut"
        success, output = await run_command(cmd)

        if not success or not output.strip():
            return "Failed to retrieve shortcut information"

        # Filter by package name if provided (using Python instead of grep)
        if package_name:
            package_found = False
            filtered_lines = []
            line_count = 0
            max_lines = 50  # Equivalent to grep -A 50

            for line in output.strip().split("\n"):
                if line.strip().startswith(f"Package: {package_name}"):
                    package_found = True
                    filtered_lines.append(line)
                    line_count = 0
                elif package_found and line_count < max_lines:
                    filtered_lines.append(line)
                    line_count += 1

            if filtered_lines:
                output = "\n".join(filtered_lines)
            else:
                return f"No shortcuts found for package: {package_name}"

        # Process the results
        result = {}

        # Extract packages with shortcuts
        packages = []
        current_package = None
        shortcuts = []

        lines = output.strip().split("\n")
        for i, line in enumerate(lines):
            line = line.strip()

            if line.startswith("Package:"):
                # Save previous package data if exists
                if current_package and shortcuts:
                    result[current_package] = {"shortcuts": shortcuts}

                # Start new package
                parts = line.split(":", 1)
                if len(parts) > 1:
                    current_package = (
                        parts[1].strip().split()[0]
                    )  # Get package name without UID
                    packages.append(current_package)
                    shortcuts = []

            # Extract shortcut info when inside a package section
            elif current_package and "ShortcutInfo" in line:
                shortcut = {}
                shortcut_id_match = re.search(r"\{id=([^,]+)", line)
                if shortcut_id_match:
                    shortcut["id"] = shortcut_id_match.group(1)

                # Continue collecting data for this shortcut - use current index instead of searching
                collect_for = 5  # Collect next 5 lines for this shortcut
                for j in range(i + 1, min(i + collect_for, len(lines))):
                    subline = lines[j].strip()

                    # Extract shortcut label
                    if "shortLabel=" in subline:
                        label_match = re.search(r"shortLabel=([^,]+)", subline)
                        if label_match:
                            shortcut["label"] = label_match.group(1).strip()

                    # Extract intent data
                    elif "intents=" in subline:
                        intent_match = re.search(r"act=([^ ]+)", subline)
                        if intent_match:
                            shortcut["action"] = intent_match.group(1)

                        component_match = re.search(r"cmp=([^ \}/]+)", subline)
                        if component_match:
                            shortcut["component"] = component_match.group(1)

                if shortcut.get("id"):
                    shortcuts.append(shortcut)

        # Add the last package
        if current_package and shortcuts:
            result[current_package] = {"shortcuts": shortcuts}

        # If we're looking for a specific package but didn't find any shortcuts
        if package_name and package_name not in result:
            return f"No shortcuts found for package: {package_name}"

        # If not looking for a specific package, include list of all packages
        if not package_name:
            result["all_packages"] = packages

        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error retrieving app shortcuts: {str(e)}"


async def push_file(local_path: str, device_path: str) -> str:
    """Copy a file from the machine running this server onto the device.

    Args:
        local_path (str): Path to the file on this machine
        device_path (str): Destination on the device, either a directory
                           ("/sdcard/Download/") or a full file path

    Returns:
        str: JSON string with operation result:
            {
                "status": "success",
                "message": str,
                "device_path": str,
                "size_bytes": int
            }
            or {"status": "error", "message": str}
    """
    if (blocked := require_writable()) is not None:
        return json.dumps({"status": "error", "message": blocked})

    if not os.path.isfile(local_path):
        return json.dumps(
            {"status": "error", "message": f"File not found: {local_path}"}
        )

    connection_status = await check_device_connection()
    if "ready" not in connection_status:
        return json.dumps({"status": "error", "message": connection_status})

    success, output = await run_command(
        f"adb push {shlex.quote(local_path)} {shlex.quote(device_path)}", timeout=600
    )

    if not success:
        return json.dumps(
            {"status": "error", "message": f"Failed to push file: {output.strip()}"}
        )

    # A destination given as a directory keeps the source file's name.
    target = (
        device_path.rstrip("/") + "/" + os.path.basename(local_path)
        if device_path.endswith("/")
        else device_path
    )

    return json.dumps(
        {
            "status": "success",
            "message": f"Pushed {local_path} to {target}",
            "device_path": target,
            "size_bytes": os.path.getsize(local_path),
        }
    )


async def pull_file(device_path: str, local_path: str) -> str:
    """Copy a file from the device to the machine running this server.

    Args:
        device_path (str): Path to the file on the device
        local_path (str): Destination on this machine, either a directory or a
                          full file path

    Returns:
        str: JSON string with operation result:
            {
                "status": "success",
                "message": str,
                "local_path": str,
                "size_bytes": int
            }
            or {"status": "error", "message": str}
    """
    connection_status = await check_device_connection()
    if "ready" not in connection_status:
        return json.dumps({"status": "error", "message": connection_status})

    success, output = await run_command(
        f"adb pull {shlex.quote(device_path)} {shlex.quote(local_path)}", timeout=600
    )

    if not success:
        return json.dumps(
            {"status": "error", "message": f"Failed to pull file: {output.strip()}"}
        )

    target = (
        os.path.join(local_path, os.path.basename(device_path))
        if os.path.isdir(local_path)
        else local_path
    )

    if not os.path.isfile(target):
        return json.dumps(
            {
                "status": "error",
                "message": f"adb reported success but {target} is missing: {output.strip()}",
            }
        )

    return json.dumps(
        {
            "status": "success",
            "message": f"Pulled {device_path} to {target}",
            "local_path": target,
            "size_bytes": os.path.getsize(target),
        }
    )


async def get_screen_info() -> str:
    """Get the device's display geometry and current rotation.

    The physical size is the panel's own resolution and never changes; the
    current size is what apps are laid out in, so it follows rotation and any
    size override set with ``wm size``. Tap coordinates are in current-size
    space.

    Returns:
        str: JSON string with display details:
            {
                "status": "success",
                "physical_size": {"width": int, "height": int},
                "current_size": {"width": int, "height": int},
                "override_size": {"width": int, "height": int} (only when set),
                "density_dpi": int,
                "rotation_degrees": int,
                "orientation": "portrait" or "landscape"
            }
            or {"status": "error", "message": str}
    """
    connection_status = await check_device_connection()
    if "ready" not in connection_status:
        return json.dumps({"status": "error", "message": connection_status})

    success, size_output = await run_command("adb shell wm size")
    if not success:
        return json.dumps(
            {
                "status": "error",
                "message": f"Failed to read screen size: {size_output.strip()}",
            }
        )

    result = {"status": "success"}

    if match := re.search(r"Physical size:\s*(\d+)x(\d+)", size_output):
        result["physical_size"] = {
            "width": int(match.group(1)),
            "height": int(match.group(2)),
        }

    if match := re.search(r"Override size:\s*(\d+)x(\d+)", size_output):
        result["override_size"] = {
            "width": int(match.group(1)),
            "height": int(match.group(2)),
        }

    success, density_output = await run_command("adb shell wm density")
    if success:
        if match := re.search(r"density:\s*(\d+)", density_output):
            result["density_dpi"] = int(match.group(1))

    success, display_output = await run_command("adb shell dumpsys window displays")
    if success:
        # cur= is the display as it stands right now, rotation and any override
        # already applied - which is the box tap coordinates are measured in.
        if match := re.search(r"cur=(\d+)x(\d+)", display_output):
            result["current_size"] = {
                "width": int(match.group(1)),
                "height": int(match.group(2)),
            }
        if match := re.search(r"mCurrentRotation=ROTATION_(\d+)", display_output):
            result["rotation_degrees"] = int(match.group(1))

    current = result.get("current_size") or result.get("physical_size")
    if current:
        result["orientation"] = (
            "landscape" if current["width"] > current["height"] else "portrait"
        )

    return json.dumps(result, indent=2)
