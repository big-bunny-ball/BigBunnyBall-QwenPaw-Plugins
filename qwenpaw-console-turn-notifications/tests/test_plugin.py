"""Focused backend and QwenPaw lifecycle regression tests."""

from __future__ import annotations

import asyncio
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from qwenpaw.runtime.hooks import HookRegistry, HookResult
from qwenpaw.runtime.phases import Phase
from qwenpaw.schemas import AgentRequest

PLUGIN_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("turn_notifications_tested", PLUGIN_DIR / "plugin.py")
backend = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backend)


def context(*, channel="console", error=None):
    return SimpleNamespace(
        request=AgentRequest.model_validate({"channel": channel, "session_id": "s"}),
        error=error,
    )


class CompletionTests(unittest.TestCase):
    def test_successful_console_turn_signals_fixed_message(self):
        event = backend.completion_event(context())
        self.assertEqual(event, {"message": "QwenPaw has completed the turn."})

    def test_non_console_and_failed_turns_do_not_notify(self):
        self.assertIsNone(backend.completion_event(context(channel="discord")))
        self.assertIsNone(backend.completion_event(context(error=RuntimeError())))

    def test_real_plugin_module_passes_qwenpaw_validation(self):
        from qwenpaw.plugins.validation import validate_plugin_module

        validate_plugin_module("turn-notifications", PLUGIN_DIR, "plugin.py")


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        from qwenpaw.plugins.registry import PluginRegistry

        self.registry = PluginRegistry()
        self.original = {
            "manager": self.registry.get_workspace_manager(),
            "http_app": self.registry.get_plugin_http_app(),
            "_startup_hooks": self.registry.get_startup_hooks(),
            "_shutdown_hooks": self.registry.get_shutdown_hooks(),
            "_workspace_created_hooks": self.registry.get_workspace_created_hooks(),
            "_http_prefix_to_plugin": dict(self.registry._http_prefix_to_plugin),
            "_http_router_registrations": list(self.registry._http_router_registrations),
        }
        # Match QwenPaw's real loader: clear routes after unregistering, and
        # mount on the existing app rather than replacing its FastAPI object.
        self.registry.unregister_plugin("turn-notifications")
        self.registry._unregister_plugin_http_routes("turn-notifications")
        self.registry.set_workspace_manager(None)
        if self.registry.get_plugin_http_app() is None:
            self.registry.set_plugin_http_app(FastAPI())

    def tearDown(self):
        self.registry.set_workspace_manager(self.original["manager"])
        self.registry.set_plugin_http_app(self.original["http_app"])
        for key in (
            "_startup_hooks",
            "_shutdown_hooks",
            "_workspace_created_hooks",
            "_http_prefix_to_plugin",
            "_http_router_registrations",
        ):
            setattr(self.registry, key, self.original[key])

    def api(self):
        from qwenpaw.plugins.api import PluginApi

        api = PluginApi("turn-notifications", {})
        api.set_registry(self.registry)
        return api

    def workspace(self):
        return SimpleNamespace(plugins=SimpleNamespace(hook_registry=HookRegistry()))

    def test_repeated_workspace_reload_leaves_one_hook(self):
        from qwenpaw.plugins.api import PluginApi

        backend.TurnNotificationsPlugin().register(self.api())
        workspace = self.workspace()
        for _ in range(3):
            for setup in self.registry.get_workspace_setup_hooks():
                setup.callback({"workspace": workspace})
            hooks = workspace.plugins.hook_registry.hooks_for(Phase.POST_RESPONSE)
            self.assertEqual(
                [hook.name for hook in hooks],
                [backend.COMPLETED_HOOK_NAME],
            )
        # QwenPaw's subsequent zero-downtime candidate setup sees no previous
        # workspace hook, but its runtime registration still runs once.
        candidate = self.workspace()
        self.registry.unregister_plugin("turn-notifications")
        self.registry._unregister_plugin_http_routes("turn-notifications")
        api = PluginApi("turn-notifications", {})
        api.set_registry(self.registry)
        backend.TurnNotificationsPlugin().register(api)
        for setup in self.registry.get_workspace_setup_hooks():
            setup.callback({"workspace": candidate})
        self.assertEqual(
            [hook.name for hook in candidate.plugins.hook_registry.hooks_for(Phase.POST_RESPONSE)],
            [backend.COMPLETED_HOOK_NAME],
        )

    def test_old_workspace_hooks_are_removed_and_others_survive(self):
        class OtherHook(backend.LifecycleHook):
            phase = Phase.POST_RESPONSE
            name = "unrelated_hook"

        old = self.workspace()
        backend.TurnNotificationsPlugin().register(self.api())
        for setup in self.registry.get_workspace_setup_hooks():
            setup.callback({"workspace": old})
        old.plugins.hook_registry.register(OtherHook())
        self.registry.set_workspace_manager(SimpleNamespace(agents={"default": old}))
        removed = backend.remove_stale_runtime_hooks()
        self.assertEqual(removed, 1)
        self.assertEqual(
            [hook.name for hook in old.plugins.hook_registry.hooks_for(Phase.POST_RESPONSE)],
            ["unrelated_hook"],
        )

    def test_completion_hook_publishes_without_response_content(self):
        plugin = backend.TurnNotificationsPlugin()
        plugin.register(self.api())
        # Obtain the actual hook through a normal workspace setup.
        workspace = self.workspace()
        for setup in self.registry.get_workspace_setup_hooks():
            setup.callback({"workspace": workspace})
        runtime_hook = workspace.plugins.hook_registry.hooks_for(Phase.POST_RESPONSE)[0]
        result = asyncio.run(runtime_hook.run(context()))
        self.assertIsInstance(result, HookResult)
        self.assertEqual(plugin.store.latest_sequence, 1)


class EventEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_subscriber_receives_only_completion_signal(self):
        plugin = backend.TurnNotificationsPlugin(keepalive_seconds=0.01)
        request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
        response = await plugin._events(request)
        stream = response.body_iterator
        self.assertIn(b"stream.ready", await anext(stream))
        plugin.store.publish()
        self.assertEqual(
            await asyncio.wait_for(anext(stream), timeout=1),
            b"event: turn.completed\ndata: {}\n\n",
        )
        await stream.aclose()
        self.assertEqual(len(plugin.store._subscribers), 0)


if __name__ == "__main__":
    unittest.main()
