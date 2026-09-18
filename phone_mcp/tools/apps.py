"""App-related phone control functions."""

import json
import os
import re
import shlex
import logging
from ..core import run_command, check_device_connection
from ..readonly import require_writable
from typing import Optional, Dict

logger = logging.getLogger("phone_mcp")

#: Special permissions ``pm grant`` refuses - they are app ops, set through
#: ``appops`` under their bare name.
APP_OPS_PERMISSIONS = frozenset(
    {
        "MANAGE_EXTERNAL_STORAGE",
        "SYSTEM_ALERT_WINDOW",
        "WRITE_SETTINGS",
        "REQUEST_INSTALL_PACKAGES",
    }
)


async def list_installed_apps(
    only_system=False, only_third_party=False, page=1, page_size=10, basic=True
):
    """List installed applications on the device with pagination support.

    Args:
        only_system (bool): If True, only show system apps
        only_third_party (bool): If True, only show third-party apps
        page (int): Page number (starts from 1)
        page_size (int): Number of items per page
        basic (bool): If True, only return basic info (faster loading, default behavior)

    Returns:
        str: JSON string containing:
            {
                "status": "success" or "error",
                "message": Error message if status is error,
                "total_count": Total number of apps,
                "total_pages": Total number of pages,
                "current_page": Current page number,
                "page_size": Number of items per page,
                "apps": [
                    {
                        "package_name": str,
                        "app_name": str,
                        "system_app": bool,
                        "version_name": str (if not basic),
                        "version_code": str (if not basic),
                        "install_time": str (if not basic)
                    },
                    ...
                ]
            }
    """
    # Ensure page and page_size are integers
    try:
        page = int(page)
        page_size = int(page_size)
    except (ValueError, TypeError):
        return json.dumps({
            "status": "error",
            "message": "Invalid page or page_size parameter. Must be integers."
        }, indent=2)

    # Check for connected device
    connection_status = await check_device_connection()
    if "ready" not in connection_status:
        return connection_status

    # Build the command based on options
    if only_system:
        cmd = "adb shell cmd package list packages -s"  # System packages only
    elif only_third_party:
        cmd = "adb shell cmd package list packages -3"  # Third-party packages only
    else:
        cmd = "adb shell cmd package list packages"  # All packages

    success, output = await run_command(cmd)

    if not success:
        return json.dumps(
            {
                "status": "error",
                "message": "Failed to get installed apps",
                "output": output,
            },
            indent=2,
        )

    # Process the output - convert package list to array
    all_packages = []
    for line in output.strip().split("\n"):
        if line.startswith("package:"):
            package_name = line[8:].strip()  # Remove "package:" prefix
            all_packages.append(package_name)

    # Calculate pagination
    total_count = len(all_packages)
    total_pages = (total_count + page_size - 1) // page_size
    
    # Validate page number
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages if total_pages > 0 else 1
    
    # Calculate slice indices for pagination
    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_count)
    
    # Get packages for current page
    current_packages = all_packages[start_idx:end_idx]
    
    # Process packages based on basic/detailed mode
    apps_info = []
    for package_name in current_packages:
        app_info = {"package_name": package_name}
        
        # Get app label (name)
        cmd = f'adb shell cmd package get-app-label {package_name}'
        success, label_output = await run_command(cmd)
        if success and label_output:
            app_info["app_name"] = label_output.strip()
        else:
            app_info["app_name"] = package_name
            
        # Check if system app
        cmd = f'adb shell pm path {package_name}'
        success, path_output = await run_command(cmd)
        app_info["system_app"] = success and "system" in path_output.lower()
        
        if not basic:
            # Get detailed info
            cmd = f'adb shell dumpsys package {package_name}'
            success, info_output = await run_command(cmd)
            if success:
                # Parse version info
                version_name = re.search(r"versionName=([^=\s]+)", info_output)
                if version_name:
                    app_info["version_name"] = version_name.group(1)
                    
                version_code = re.search(r"versionCode=(\d+)", info_output)
                if version_code:
                    app_info["version_code"] = version_code.group(1)
                    
                # Parse install time
                first_install = re.search(r"firstInstallTime=([^=\s]+)", info_output)
                if first_install:
                    app_info["install_time"] = first_install.group(1)
        
        apps_info.append(app_info)
    
    # Create the final result
    result = {
        "status": "success",
        "total_count": total_count,
        "total_pages": total_pages,
        "current_page": page,
        "page_size": page_size,
        "apps": apps_info
    }
    
    if only_system:
        result["type"] = "system"
    elif only_third_party:
        result["type"] = "third_party"
    
    return json.dumps(result, indent=2)


async def list_app_activities(package_name: str):
    """List all activities in a specific app package.

    Args:
        package_name (str): Package name of the app

    Returns:
        str: JSON string with list of activities or error message
    """
    # Check for connected device
    connection_status = await check_device_connection()
    if "ready" not in connection_status:
        return connection_status

    # Build the command to query activities
    cmd = f"adb shell cmd package query-activities -a android.intent.action.MAIN -c android.intent.category.LAUNCHER --components {package_name}"
    success, output = await run_command(cmd)

    if not success:
        return json.dumps(
            {
                "status": "error",
                "message": f"Failed to get activities for {package_name}",
                "output": output,
            },
            indent=2,
        )

    activities = []

    # Process the output - extract activities
    for line in output.strip().split("\n"):
        if package_name in line:
            # Format: packageName/activityName
            parts = line.strip().split()
            if len(parts) > 0:
                activity = parts[0].strip()
                activities.append(activity)

    return json.dumps(
        {
            "status": "success",
            "package": package_name,
            "count": len(activities),
            "activities": activities,
        },
        indent=2,
    )


async def terminate_app(package_name: str):
    """Force stop an application on the device.

    Args:
        package_name (str): Package name of the app to terminate

    Returns:
        str: Success or error message
    """
    if (blocked := require_writable()) is not None:
        return blocked
    # Check for connected device
    connection_status = await check_device_connection()
    if "ready" not in connection_status:
        return connection_status

    # Verify the package exists
    cmd = f"adb shell pm list packages | grep {package_name}"
    success, output = await run_command(cmd)

    if not success or package_name not in output:
        # Try an exact match instead of grep
        verify_cmd = "adb shell pm list packages"
        success, verify_output = await run_command(verify_cmd)

        package_exists = False
        if success:
            for line in verify_output.strip().split("\n"):
                if line.strip() == f"package:{package_name}":
                    package_exists = True
                    break

        if not package_exists:
            return f"Package {package_name} not found on device"

    # Force stop the application
    cmd = f"adb shell am force-stop {package_name}"
    success, output = await run_command(cmd)

    if success:
        return f"Successfully terminated {package_name}"
    else:
        return f"Failed to terminate app: {output}"


async def install_app(
    apk_path: str, reinstall: bool = True, grant_permissions: bool = False
) -> str:
    """Install an APK from the local machine onto the device.

    Args:
        apk_path (str): Path to the .apk file on the machine running this server
        reinstall (bool): Keep the existing app's data when a previous version is
                          installed (``adb install -r``). Defaults to True.
        grant_permissions (bool): Grant all runtime permissions the manifest
                                  declares (``adb install -g``). Defaults to False.

    Returns:
        str: JSON string with operation result:
            {
                "status": "success",
                "message": "Installed <apk_path>",
                "package_name": str (when it could be read from the APK)
            }
            or {"status": "error", "message": str}
    """
    if (blocked := require_writable()) is not None:
        return json.dumps({"status": "error", "message": blocked})

    if not os.path.isfile(apk_path):
        return json.dumps(
            {"status": "error", "message": f"APK not found: {apk_path}"}
        )

    connection_status = await check_device_connection()
    if "ready" not in connection_status:
        return json.dumps({"status": "error", "message": connection_status})

    flags = ""
    if reinstall:
        flags += " -r"
    if grant_permissions:
        flags += " -g"

    # An APK of a few hundred MB over USB outlasts the default command timeout.
    # adb writes both its progress and its verdict to stdout and then exits
    # non-zero on failure, and run_command keeps only stderr in that case, so
    # the streams are merged and the exit status neutralised - the verdict in
    # the text is what says whether it worked.
    success, output = await run_command(
        f"adb install{flags} {shlex.quote(apk_path)} 2>&1 || true", timeout=600
    )

    if not success or "Success" not in output:
        return json.dumps(
            {"status": "error", "message": f"Failed to install app: {output.strip()}"}
        )

    result = {"status": "success", "message": f"Installed {apk_path}"}

    package_name = await _package_name_of_apk(apk_path)
    if package_name:
        result["package_name"] = package_name

    return json.dumps(result)


async def _package_name_of_apk(apk_path: str) -> Optional[str]:
    """Read the package name out of an APK.

    The name lives in the binary AndroidManifest.xml, which needs a real parser,
    so this asks the build tools. They are frequently not installed - hence
    None rather than an error, and a caller that only got a path still gets its
    install confirmed.
    """
    success, output = await run_command(f"aapt dump badging {shlex.quote(apk_path)}")
    if success:
        if match := re.search(r"package: name='([^']+)'", output):
            return match.group(1)

    success, output = await run_command(
        f"aapt2 dump packagename {shlex.quote(apk_path)}"
    )
    if success and output.strip():
        return output.strip().splitlines()[0]

    return None


async def uninstall_app(package_name: str, keep_data: bool = False) -> str:
    """Uninstall an application from the device.

    Args:
        package_name (str): Package name of the app to remove
        keep_data (bool): Keep the app's data and cache directories
                          (``adb uninstall -k``). Defaults to False.

    Returns:
        str: JSON string with operation result:
            {"status": "success", "message": "Uninstalled <package_name>"}
            or {"status": "error", "message": str}
    """
    if (blocked := require_writable()) is not None:
        return json.dumps({"status": "error", "message": blocked})

    connection_status = await check_device_connection()
    if "ready" not in connection_status:
        return json.dumps({"status": "error", "message": connection_status})

    flags = " -k" if keep_data else ""
    # Same as install: the verdict is on stdout, the exit status non-zero.
    success, output = await run_command(
        f"adb uninstall{flags} {shlex.quote(package_name)} 2>&1 || true"
    )

    if not success or "Success" not in output:
        return json.dumps(
            {
                "status": "error",
                "message": f"Failed to uninstall app: {output.strip()}",
            }
        )

    return json.dumps(
        {"status": "success", "message": f"Uninstalled {package_name}"}
    )


async def grant_permission(package_name: str, permission: str) -> str:
    """Grant a permission to an installed application.

    Runtime permissions go through ``pm grant``. The all-files permission
    MANAGE_EXTERNAL_STORAGE is not a runtime permission and ``pm grant``
    rejects it, so it is set through ``appops`` instead.

    Args:
        package_name (str): Package name of the app
        permission (str): Permission to grant, either fully qualified
                          ("android.permission.READ_EXTERNAL_STORAGE") or bare
                          ("READ_EXTERNAL_STORAGE")

    Returns:
        str: JSON string with operation result:
            {"status": "success", "message": str}
            or {"status": "error", "message": str}
    """
    if (blocked := require_writable()) is not None:
        return json.dumps({"status": "error", "message": blocked})

    connection_status = await check_device_connection()
    if "ready" not in connection_status:
        return json.dumps({"status": "error", "message": connection_status})

    bare_name = permission.rsplit(".", 1)[-1]

    if bare_name in APP_OPS_PERMISSIONS:
        cmd = (
            f"adb shell appops set {shlex.quote(package_name)} "
            f"{shlex.quote(bare_name)} allow"
        )
    else:
        qualified = (
            permission if "." in permission else f"android.permission.{permission}"
        )
        cmd = (
            f"adb shell pm grant {shlex.quote(package_name)} {shlex.quote(qualified)}"
        )

    success, output = await run_command(cmd)

    # pm grant prints its complaints on stderr and still exits non-zero, but
    # appops stays silent on both streams when it accepts the op.
    if not success:
        # pm grant answers a bad permission with a Java stack trace; only its
        # first line says anything a caller can act on.
        reason = output.strip().splitlines()
        reason = reason[0] if reason else "no output from adb"
        return json.dumps(
            {"status": "error", "message": f"Failed to grant permission: {reason}"}
        )

    return json.dumps(
        {
            "status": "success",
            "message": f"Granted {permission} to {package_name}",
        }
    )


async def open_file(
    device_path: str,
    package_name: Optional[str] = None,
    activity_name: Optional[str] = None,
    mime_type: Optional[str] = None,
) -> str:
    """Open a file that is already on the device, optionally in a chosen app.

    Sends an ACTION_VIEW intent for the file. Without a package name the device
    picks the handler itself, which may raise its own chooser dialog; naming a
    package and activity opens it in that app directly.

    Args:
        device_path (str): Absolute path on the device, e.g. "/sdcard/Download/book.epub"
        package_name (str, optional): Package to open the file with
        activity_name (str, optional): Activity within that package. A leading dot
                                       is resolved against the package, as in adb.
                                       Ignored without package_name.
        mime_type (str, optional): MIME type to declare, e.g. "application/epub+zip".
                                   Some apps only match an intent that carries one.

    Returns:
        str: JSON string with operation result:
            {"status": "success", "message": "Opened <device_path>"}
            or {"status": "error", "message": str}

    Examples:
        # Let the device choose the app
        result = await open_file("/sdcard/Download/book.epub")

        # Open in a named app
        result = await open_file(
            "/sdcard/Download/book.epub",
            "com.foobnix.pro.pdf.reader",
            "com.foobnix.OpenerActivity",
            "application/epub+zip",
        )
    """
    if (blocked := require_writable()) is not None:
        return json.dumps({"status": "error", "message": blocked})

    connection_status = await check_device_connection()
    if "ready" not in connection_status:
        return json.dumps({"status": "error", "message": connection_status})

    success, _ = await run_command(f"adb shell ls {shlex.quote(device_path)}")
    if not success:
        return json.dumps(
            {
                "status": "error",
                "message": f"File not found on device: {device_path}",
            }
        )

    cmd = (
        "adb shell am start -a android.intent.action.VIEW "
        f"-d {shlex.quote('file://' + device_path)}"
    )
    if mime_type:
        cmd += f" -t {shlex.quote(mime_type)}"
    if package_name:
        component = (
            f"{package_name}/{activity_name}" if activity_name else package_name
        )
        cmd += f" -n {shlex.quote(component)}"

    success, output = await run_command(cmd)

    # am start reports a missing component or an unhandled intent as "Error:"
    # on stdout while still exiting zero.
    if not success or "Error:" in output:
        return json.dumps(
            {"status": "error", "message": f"Failed to open file: {output.strip()}"}
        )

    return json.dumps({"status": "success", "message": f"Opened {device_path}"})


async def set_alarm(hour: int, minute: int, label: str = "Alarm") -> str:
    """Set an alarm on the phone.

    Creates a new alarm with the specified time and label using the default
    clock application.

    Args:
        hour (int): Hour in 24-hour format (0-23)
        minute (int): Minute (0-59)
        label (str): Optional label for the alarm (default: "Alarm")

    Returns:
        str: Success message if the alarm was set, or an error message
             if the alarm could not be created.
    """
    if (blocked := require_writable()) is not None:
        return blocked
    # Check for connected device
    connection_status = await check_device_connection()
    if "ready" not in connection_status:
        return connection_status

    # Validate time inputs
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return "Invalid time. Hour must be 0-23 and minute must be 0-59."

    # Format time for display
    time_str = f"{hour:02d}:{minute:02d}"
    escaped_label = label.replace("'", "\\'")

    # Create the alarm using the alarm clock intent
    cmd = (
        f"adb shell am start -a android.intent.action.SET_ALARM "
        f"-e android.intent.extra.alarm.HOUR {hour} "
        f"-e android.intent.extra.alarm.MINUTES {minute} "
        f"-e android.intent.extra.alarm.MESSAGE '{escaped_label}' "
        f"-e android.intent.extra.alarm.SKIP_UI true"
    )

    success, output = await run_command(cmd)

    if success:
        return f"Alarm set for {time_str} with label '{label}'"
    else:
        return f"Failed to set alarm: {output}"


async def launch_app_activity(package_name: str, activity_name: str = None) -> str:
    """Launch an app using package name and optionally an activity name
    
    This function uses adb to start an application on the device either by package name
    or by specifying both package and activity. It provides reliable app launching across
    different Android devices and versions.
    
    Args:
        package_name (str): The package name of the app to launch (e.g., "com.android.contacts")
        activity_name (str): The specific activity to launch. If not provided,
                                      launches the app's main activity. Defaults to None.
    
    Returns:
        str: JSON string with operation result:
            For successful operations:
                {
                    "status": "success",
                    "message": "Successfully launched <package_name>"
                }
            
            For failed operations:
                {
                    "status": "error",
                    "message": "Failed to launch app: <error details>"
                }
    
    Examples:
        # Launch an app using just the package name
        result = await launch_app_activity("com.android.contacts")
        
        # Launch a specific activity within an app
        result = await launch_app_activity("com.android.dialer", "com.android.dialer.DialtactsActivity")
        
        # Launch Android settings
        result = await launch_app_activity("com.android.settings")
    """
    if (blocked := require_writable()) is not None:
        return json.dumps({"status": "error", "message": blocked})
    try:
        if activity_name:
            # Launch specific activity
            cmd = f"adb shell am start -n {package_name}/{activity_name}"
        else:
            # Launch app's main activity
            cmd = f"adb shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
        
        success, output = await run_command(cmd)
        
        if success:
            return json.dumps({
                "status": "success",
                "message": f"Successfully launched {package_name}"
            })
        else:
            return json.dumps({
                "status": "error",
                "message": f"Failed to launch app: {output}"
            })
    except Exception as e:
        logger.error(f"Error launching app {package_name}: {str(e)}")
        return json.dumps({
            "status": "error",
            "message": f"Failed to launch app: {str(e)}"
        })


async def launch_intent(intent_action: str, intent_type: Optional[str] = None, extras: Optional[Dict[str, str]] = None) -> str:
    """Launch an activity using Android intent system
    
    This function allows launching activities using Android's intent system, which can be used
    to perform various actions like opening the contacts app in "add new contact" mode,
    opening URLs, or sharing content between apps.
    
    Args:
        intent_action (str): The action to perform (e.g., "android.intent.action.INSERT",
                          "android.intent.action.VIEW", "android.intent.action.SEND")
        intent_type (str, optional): The MIME type for the intent (e.g., "vnd.android.cursor.dir/contact",
                                  "text/plain", "image/jpeg"). Defaults to None.
        extras (Dict[str, str], optional): Extra data to pass with the intent as key-value pairs.
                                        Useful for pre-populating fields or passing data. Defaults to None.
    
    Returns:
        str: JSON string with operation result:
            For successful operations:
                {
                    "status": "success",
                    "message": "Successfully launched intent: <intent_action>"
                }
            
            For failed operations:
                {
                    "status": "error",
                    "message": "Failed to launch intent: <error details>"
                }
    
    Examples:
        # Open contacts app in "add new contact" mode
        extras = {"name": "John Doe", "phone": "1234567890"}
        result = await launch_intent(
            "android.intent.action.INSERT", 
            "vnd.android.cursor.dir/contact", 
            extras
        )
        
        # Open URL in browser
        result = await launch_intent(
            "android.intent.action.VIEW",
            None,
            {"uri": "https://www.example.com"}
        )
        
        # Share text
        result = await launch_intent(
            "android.intent.action.SEND",
            "text/plain",
            {"android.intent.extra.TEXT": "Hello world!"}
        )
    """
    try:
        # Construct base command
        cmd = f"adb shell am start -a {intent_action}"
        
        # Add type if provided
        if intent_type:
            cmd += f" -t {intent_type}"
        
        # Add extras if provided
        if extras:
            for key, value in extras.items():
                # Escape quotes in value
                value = value.replace('"', '\\"')
                cmd += f' --es {key} "{value}"'
        
        success, output = await run_command(cmd)
        
        if success:
            return json.dumps({
                "status": "success",
                "message": f"Successfully launched intent: {intent_action}"
            })
        else:
            return json.dumps({
                "status": "error",
                "message": f"Failed to launch intent: {output}"
            })
    except Exception as e:
        logger.error(f"Error launching intent {intent_action}: {str(e)}")
        return json.dumps({
            "status": "error",
            "message": f"Failed to launch intent: {str(e)}"
        })
