# -*- coding: utf-8 -*-
"""Local browser notifications for completed console turns."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from qwenpaw.hooks.base import LifecycleHook
from qwenpaw.runtime.hooks import HookContext, HookResult
from qwenpaw.runtime.phases import Phase

logger = logging.getLogger(__name__)

PLUGIN_ID = "turn-notifications"
COMPLETED_HOOK_NAME = "turn_notifications_completed"
SUBSCRIBER_LIMIT = 32


def completion_event(ctx: HookContext) -> dict[str, Any] | None:
    """Signal a successful console turn without reading its response."""
    if ctx.error is not None:
        return None
    if getattr(ctx.request, "channel", None) != "console":
        return None
    return {"message": "QwenPaw has completed the turn."}


class CompletionStore:
    """Fan out completion signals; no response content or history is kept."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self.latest_sequence = 0

    def publish(self) -> None:
        self.latest_sequence += 1
        for queue in tuple(self._subscribers):
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass

    def subscribe(self) -> asyncio.Queue:
        # Concurrent streaming responses share QwenPaw's single event loop,
        # so the limit check and insertion cannot interleave.
        if len(self._subscribers) >= SUBSCRIBER_LIMIT:
            raise RuntimeError("Too many notification streams")
        queue: asyncio.Queue = asyncio.Queue(maxsize=128)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)


def remove_stale_runtime_hooks(workspace_info: dict | None = None) -> int:
    """Remove only this plugin's old hooks before a hot reload.

    QwenPaw 2.2.2.post1 does not unregister runtime hooks from existing
    workspaces when unloading a plugin. Duplicate names break its current
    topological sorter, so cleanup must be both forward and backward
    compatible with installations made before this guard existed.
    """
    from qwenpaw.plugins.registry import PluginRegistry

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
                if getattr(hook, "name", None) != COMPLETED_HOOK_NAME
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
    """Publish successful console completions to open console tabs."""

    def __init__(self, *, keepalive_seconds: float = 15) -> None:
        self.store = CompletionStore()
        self.keepalive_seconds = keepalive_seconds
        self.stream_id = uuid.uuid4().hex

    def _router(self) -> APIRouter:
        router = APIRouter()

        @router.get("/events")
        async def events(request: Request) -> StreamingResponse:
            return await self._events(request)

        @router.get("/health")
        async def health() -> dict[str, Any]:
            return {
                "ok": True,
                "plugin": PLUGIN_ID,
                "latest_sequence": self.store.latest_sequence,
                "stream_id": self.stream_id,
            }

        return router

    async def _events(self, request: Request) -> StreamingResponse:
        queue = self.store.subscribe()

        async def stream() -> AsyncIterator[bytes]:
            try:
                yield b"retry: 3000\nevent: stream.ready\ndata: {}\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        await asyncio.wait_for(
                            queue.get(),
                            timeout=self.keepalive_seconds,
                        )
                    except TimeoutError:
                        yield b": keep-alive\n\n"
                        continue
                    yield b"event: turn.completed\ndata: {}\n\n"
            finally:
                self.store.unsubscribe(queue)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
                "X-Stream-Id": self.stream_id,
            },
        )

    def register(self, api: Any) -> None:
        plugin = self
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
                    event = completion_event(ctx)
                    if event is not None:
                        plugin.store.publish()
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
            "turn_notifications_runtime_cleanup",
            remove_stale_runtime_hooks,
            priority=64,
        )
        api.register_shutdown_hook(
            "turn_notifications_runtime_cleanup",
            remove_stale_runtime_hooks,
        )
        api.register_workspace_created_hook(
            "turn_notifications_workspace_cleanup",
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
        logger.info("Turn notifications registered; response data stays in memory")


plugin = TurnNotificationsPlugin()

__all__ = [
    "CompletionStore",
    "TurnNotificationsPlugin",
    "completion_event",
    "remove_stale_runtime_hooks",
    "plugin",
]
