# -*- coding: utf-8 -*-
"""Native Windows toast notifications for completed console turns.

Version 1 targets Windows only. It shows one fixed notification:

    QwenPaw has completed the turn.

There is no browser notification, no frontend entry, no SSE stream, and no
storage of response content. The toast is produced by Windows itself through
WinRT, so it appears even when no console tab is open.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import sys
from typing import Any

from fastapi import APIRouter
from qwenpaw.hooks.base import LifecycleHook
from qwenpaw.runtime.hooks import HookContext, HookResult
from qwenpaw.runtime.phases import Phase

logger = logging.getLogger(__name__)

PLUGIN_ID = "qwenpaw-console-turn-notifications"
COMPLETED_HOOK_NAME = "qwenpaw_console_turn_notification"

# A stable AppUserModelId gives the toast its own identity ("QwenPaw") instead
# of borrowing the name of whatever process happens to raise it.
APP_USER_MODEL_ID = "QwenPaw.ConsoleTurnNotifications"
APP_DISPLAY_NAME = "QwenPaw"
TITLE = "QwenPaw"
MESSAGE = "QwenPaw has completed the turn."

# Windows may take a moment to cold-start PowerShell and WinRT.
TOAST_TIMEOUT_SECONDS = 20.0

_CREATE_NO_WINDOW = 0x08000000

_TOAST_SCRIPT = """
$ErrorActionPreference = 'Stop'
$appId = '{app_id}'
$key = 'HKCU:\\Software\\Classes\\AppUserModelId\\' + $appId
if (-not (Test-Path $key)) {{
    New-Item -Path $key -Force | Out-Null
    Set-ItemProperty -Path $key -Name DisplayName -Value '{app_name}'
}}
[void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime]
[void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime]
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml('{payload}')
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
"""


def completion_event(ctx: HookContext) -> dict[str, Any] | None:
    """Return the fixed notification payload, or None for other turns."""
    if ctx.error is not None:
        return None
    if getattr(ctx.request, "channel", None) != "console":
        return None
    return {"title": TITLE, "message": MESSAGE}


def toast_xml(title: str = TITLE, message: str = MESSAGE) -> str:
    """Build generic toast XML, escaping the dynamic text."""
    def escape(value: str) -> str:
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    return (
        "<toast><visual><binding template=\"ToastGeneric\">"
        f"<text>{escape(title)}</text>"
        f"<text>{escape(message)}</text>"
        "</binding></visual></toast>"
    )


def build_powershell_command(
    title: str = TITLE,
    message: str = MESSAGE,
) -> list[str]:
    """Build a self-contained, quoting-safe PowerShell invocation."""
    payload = toast_xml(title, message).replace("'", "''")
    script = _TOAST_SCRIPT.format(
        app_id=APP_USER_MODEL_ID,
        app_name=APP_DISPLAY_NAME.replace("'", "''"),
        payload=payload,
    )
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-WindowStyle",
        "Hidden",
        "-EncodedCommand",
        encoded,
    ]


def notifications_supported() -> bool:
    """Version 1 supports Windows only."""
    return sys.platform == "win32"


async def show_toast(title: str = TITLE, message: str = MESSAGE) -> bool:
    """Raise a native Windows toast. Never raises for notification failures."""
    if not notifications_supported():
        logger.info("Turn notifications v1 supports Windows only; toast skipped")
        return False
    try:
        process = await asyncio.create_subprocess_exec(
            *build_powershell_command(title, message),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            creationflags=_CREATE_NO_WINDOW,
        )
        _, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=TOAST_TIMEOUT_SECONDS,
        )
        if process.returncode != 0:
            logger.warning(
                "Turn notification toast failed (exit %s): %s",
                process.returncode,
                stderr.decode("utf-8", "replace").strip()[:500],
            )
            return False
        return True
    except (OSError, asyncio.TimeoutError) as exc:
        logger.warning("Turn notification toast could not be shown: %s", exc)
        return False


def remove_stale_runtime_hooks(workspace_info: dict | None = None) -> int:
    """Remove only this plugin's old hooks before a hot reload.

    QwenPaw 2.2.2.post1 does not unregister runtime hooks from existing
    workspaces when unloading a plugin. Duplicate names break its current
    topological sorter, so cleanup must accept both the old and new names
    from installations made before the rename.
    """
    from qwenpaw.plugins.registry import PluginRegistry

    stale = {COMPLETED_HOOK_NAME, "turn_notifications_completed"}
    if workspace_info is not None and workspace_info.get("workspace") is not None:
        workspaces = [workspace_info["workspace"]]
    else:
        manager = PluginRegistry().get_workspace_manager()
        if manager is None:
            return 0
        workspaces = list(getattr(manager, "agents", {}).values())
    removed = 0
    for workspace in workspaces:
        plugins = getattr(workspace, "plugins", None)
        registry = getattr(plugins, "hook_registry", None)
        if registry is None:
            continue
        phases = getattr(registry, "_by_phase", {})
        for phase, hooks in list(phases.items()):
            retained = [
                hook for hook in hooks
                if getattr(hook, "name", None) not in stale
            ]
            removed += len(hooks) - len(retained)
            if retained:
                phases[phase] = retained
            else:
                phases.pop(phase, None)
        # Hook ordering is computed once and cached by phase.
        getattr(registry, "_sorted_cache", {}).clear()
    if removed:
        logger.info("Removed %d stale turn-notification runtime hooks", removed)
    return removed


class TurnNotificationsPlugin:
    """Show a native Windows toast when a console turn completes."""

    def _router(self) -> APIRouter:
        router = APIRouter()

        @router.get("/health")
        async def health() -> dict[str, Any]:
            return {
                "ok": True,
                "plugin": PLUGIN_ID,
                "platform_supported": notifications_supported(),
                "message": MESSAGE,
            }

        return router

    def register(self, api: Any) -> None:
        # Hot unload cannot invoke a cleanup callback that the previous
        # version did not have. Clear that version's stale hooks now, before
        # the subsequent workspace-replacement hooks are registered.
        remove_stale_runtime_hooks()

        class CompletedTurnHook(LifecycleHook):
            phase = Phase.POST_RESPONSE
            name = COMPLETED_HOOK_NAME
            priority = 100

            async def run(self, ctx: HookContext) -> HookResult:
                try:
                    if completion_event(ctx) is not None:
                        await show_toast()
                except Exception:  # Never turn a notification into a failed turn.
                    logger.warning(
                        "Turn notification could not be published",
                        exc_info=True,
                    )
                return HookResult()

        # Run before PluginApi's priority-65 runtime registration. This
        # repairs duplicates from older hot installs; future shutdowns also
        # remove the hook through the callback registered below.
        api.register_startup_hook(
            "qwenpaw_console_turn_notification_cleanup",
            remove_stale_runtime_hooks,
            priority=64,
        )
        api.register_shutdown_hook(
            "qwenpaw_console_turn_notification_cleanup",
            remove_stale_runtime_hooks,
        )
        api.register_workspace_created_hook(
            "qwenpaw_console_turn_notification_workspace_cleanup",
            remove_stale_runtime_hooks,
            priority=64,
            reload_safe=True,
        )
        api.register_runtime_hook(CompletedTurnHook())
        api.register_http_router(
            self._router(),
            prefix="/turn-notifications",
            tags=["turn-notifications"],
        )
        logger.info(
            "Console turn notifications registered (native Windows toast, v1)"
        )


plugin = TurnNotificationsPlugin()

__all__ = [
    "TurnNotificationsPlugin",
    "build_powershell_command",
    "completion_event",
    "notifications_supported",
    "remove_stale_runtime_hooks",
    "show_toast",
    "toast_xml",
    "plugin",
]
