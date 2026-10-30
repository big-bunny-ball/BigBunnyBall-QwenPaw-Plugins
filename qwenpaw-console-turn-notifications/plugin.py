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
import time
from typing import Any

from fastapi import APIRouter
from qwenpaw.hooks.base import LifecycleHook
from qwenpaw.runtime.hooks import HookContext, HookResult
from qwenpaw.runtime.phases import Phase

logger = logging.getLogger(__name__)

PLUGIN_ID = "qwenpaw-console-turn-notifications"
COMPLETED_HOOK_NAME = "qwenpaw_console_turn_notification"
# Hook names shipped before the rename; still cleaned up on install.
LEGACY_HOOK_NAMES = ("turn_notifications_completed",)

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

# In-memory activity counters, exposed by /health. They make a silent
# notification failure observable instead of invisible.
STATS: dict[str, Any] = {
    "hook_runs": 0,
    "skipped": 0,
    "attempts": 0,
    "successes": 0,
    "failures": 0,
    "last_channel": None,
    "last_attempt_at": None,
    "last_success_at": None,
    "last_error": None,
}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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
    STATS["attempts"] += 1
    STATS["last_attempt_at"] = _now()
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
            error = stderr.decode("utf-8", "replace").strip()[:500]
            STATS["failures"] += 1
            STATS["last_error"] = f"exit {process.returncode}: {error}"
            logger.warning(
                "Turn notification toast failed (exit %s): %s",
                process.returncode,
                error,
            )
            return False
        STATS["successes"] += 1
        STATS["last_success_at"] = _now()
        return True
    except Exception as exc:  # noqa: BLE001 - notifications must never raise
        STATS["failures"] += 1
        STATS["last_error"] = f"{type(exc).__name__}: {exc}"
        logger.warning("Turn notification toast could not be shown: %s", exc)
        return False


class CompletedTurnHook(LifecycleHook):
    """Show exactly one toast per successful console turn."""

    phase = Phase.POST_RESPONSE
    name = COMPLETED_HOOK_NAME
    priority = 100

    async def run(self, ctx: HookContext) -> HookResult:
        STATS["hook_runs"] += 1
        STATS["last_channel"] = getattr(ctx.request, "channel", None)
        try:
            if completion_event(ctx) is None:
                STATS["skipped"] += 1
                return HookResult()
            await show_toast()
        except Exception:  # Never turn a notification into a failed turn.
            STATS["failures"] += 1
            logger.warning(
                "Turn notification could not be published", exc_info=True
            )
        return HookResult()


def _live_workspaces() -> dict[str, Any]:
    from qwenpaw.plugins.registry import PluginRegistry

    manager = PluginRegistry().get_workspace_manager()
    if manager is None:
        return {}
    return dict(getattr(manager, "agents", {}) or {})


def _hook_registry(workspace: Any) -> Any:
    return getattr(getattr(workspace, "plugins", None), "hook_registry", None)


def _named_hooks(registry: Any) -> list[Any]:
    """Read this plugin's hooks without triggering the ordering sort.

    ``HookRegistry.hooks_for()`` runs ``_topo_sort`` and raises on duplicates,
    so diagnostics must inspect ``_by_phase`` directly.
    """
    return [
        hook
        for hook in getattr(registry, "_by_phase", {}).get(Phase.POST_RESPONSE, [])
        if getattr(hook, "name", None) == COMPLETED_HOOK_NAME
    ]


def hook_present(workspace: Any) -> bool:
    registry = _hook_registry(workspace)
    if registry is None:
        return False
    return bool(_named_hooks(registry))


def _drop_named_hooks(registry: Any, names: set[str], keep: int = 0) -> int:
    """Remove same-named hooks, optionally keeping ``keep`` of them.

    ``HookRegistry._topo_sort`` keys hooks by name (``{h.name: h}``) but then
    compares ``len(result)`` against ``len(hooks)``. Two hooks sharing a name
    therefore always raise ``HookCycleError``, so duplicates must never exist.
    """
    removed = 0
    phases = getattr(registry, "_by_phase", {})
    for phase, hooks in list(phases.items()):
        retained: list[Any] = []
        seen: dict[str, int] = {}
        for hook in hooks:
            name = getattr(hook, "name", None)
            if name in names:
                seen[name] = seen.get(name, 0) + 1
                if seen[name] <= keep:
                    retained.append(hook)
                else:
                    removed += 1
                continue
            retained.append(hook)
        if retained:
            phases[phase] = retained
        else:
            phases.pop(phase, None)
    if removed:
        # Hook ordering is computed once and cached by phase.
        getattr(registry, "_sorted_cache", {}).clear()
    return removed


def remove_stale_runtime_hooks(workspace_info: dict | None = None) -> int:
    """Remove every trace of this plugin's runtime hook.

    QwenPaw 2.2.2.post1 does not unregister runtime hooks from existing
    workspaces when unloading a plugin, so a hot reinstall can leave two
    identically named hooks behind. Cleanup must accept the pre-rename name
    as well as the current one.
    """
    stale = {COMPLETED_HOOK_NAME, *LEGACY_HOOK_NAMES}
    if workspace_info is not None and workspace_info.get("workspace") is not None:
        workspaces = [workspace_info["workspace"]]
    else:
        workspaces = list(_live_workspaces().values())
    removed = 0
    for workspace in workspaces:
        registry = _hook_registry(workspace)
        if registry is None:
            continue
        removed += _drop_named_hooks(registry, stale)
    if removed:
        logger.info("Removed %d stale turn-notification runtime hooks", removed)
    return removed


def count_hooks(workspace: Any) -> int:
    registry = _hook_registry(workspace)
    if registry is None:
        return 0
    return len(_named_hooks(registry))


def ensure_hook_installed() -> dict[str, int]:
    """Guarantee exactly one runtime hook per live workspace.

    Manual repair only. This must never run during plugin registration: the
    framework installs the same hook from its own priority-65 startup
    callback, so adding one here would create a duplicate and trip
    ``HookCycleError`` on the next turn.
    """
    status: dict[str, int] = {}
    for agent_id, workspace in _live_workspaces().items():
        registry = _hook_registry(workspace)
        if registry is None:
            status[str(agent_id)] = 0
            continue
        # Collapse any duplicates first, then add one only if none survive.
        _drop_named_hooks(registry, {COMPLETED_HOOK_NAME}, keep=1)
        if count_hooks(workspace) == 0:
            try:
                registry.register(CompletedTurnHook())
            except Exception:  # noqa: BLE001 - report instead of crashing
                logger.warning(
                    "Could not restore turn-notification hook on %s",
                    agent_id,
                    exc_info=True,
                )
        status[str(agent_id)] = count_hooks(workspace)
    return status


class TurnNotificationsPlugin:
    """Show a native Windows toast when a console turn completes."""

    def _router(self) -> APIRouter:
        router = APIRouter()

        @router.get("/health")
        async def health(repair: int = 0) -> dict[str, Any]:
            if repair:
                ensure_hook_installed()
            workspaces = _live_workspaces()
            return {
                "ok": True,
                "plugin": PLUGIN_ID,
                "platform_supported": notifications_supported(),
                "message": MESSAGE,
                # A count above 1 means a hook-ordering cycle is imminent.
                "hook_counts": {
                    str(agent_id): count_hooks(workspace)
                    for agent_id, workspace in workspaces.items()
                },
                "stats": dict(STATS),
            }

        return router

    def register(self, api: Any) -> None:
        plugin = self

        # Hot unload cannot invoke a cleanup callback that the previous
        # version did not have. Clear that version's stale hooks now, before
        # the subsequent workspace-replacement hooks are registered.
        remove_stale_runtime_hooks()

        # Run before PluginApi's priority-65 runtime registration so a hot
        # reinstall never leaves two identically named hooks behind. This
        # callback must ONLY remove: the framework installs the hook itself
        # at priority 65, so adding one here would create a duplicate.
        api.register_startup_hook(
            "qwenpaw_console_turn_notification_cleanup",
            remove_stale_runtime_hooks,
            priority=64,
        )
        # Deliberately no global shutdown hook: stripping hooks from every
        # live workspace on shutdown removed the hook the running workspace
        # still needed, and nothing re-added it. Duplicate cleanup happens at
        # startup instead, which is the only moment it is required.
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
    "CompletedTurnHook",
    "STATS",
    "TurnNotificationsPlugin",
    "build_powershell_command",
    "completion_event",
    "count_hooks",
    "ensure_hook_installed",
    "hook_present",
    "notifications_supported",
    "remove_stale_runtime_hooks",
    "show_toast",
    "toast_xml",
    "plugin",
]
