"""Backend, lifecycle and manifest tests for console turn notifications."""

from __future__ import annotations

import asyncio
import base64
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from qwenpaw.runtime.hooks import HookRegistry, HookResult
from qwenpaw.runtime.phases import Phase
from qwenpaw.schemas import AgentRequest

PLUGIN_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "console_turn_notifications_tested", PLUGIN_DIR / "plugin.py"
)
backend = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backend)

MANIFEST = json.loads((PLUGIN_DIR / "plugin.json").read_text(encoding="utf-8"))


def context(*, channel="console", error=None):
    return SimpleNamespace(
        request=AgentRequest.model_validate({"channel": channel, "session_id": "s"}),
        error=error,
    )


class CompletionTests(unittest.TestCase):
    def test_successful_console_turn_uses_fixed_text(self):
        event = backend.completion_event(context())
        self.assertEqual(
            event,
            {"title": "QwenPaw", "message": "QwenPaw has completed the turn."},
        )

    def test_non_console_and_failed_turns_do_not_notify(self):
        self.assertIsNone(backend.completion_event(context(channel="discord")))
        self.assertIsNone(backend.completion_event(context(error=RuntimeError())))

    def test_toast_xml_escapes_dynamic_text(self):
        xml = backend.toast_xml("A & B", '<script>"x"</script>')
        self.assertIn("A &amp; B", xml)
        self.assertIn("&lt;script&gt;", xml)
        self.assertNotIn("<script>", xml)
        self.assertIn('template="ToastGeneric"', xml)


class CommandTests(unittest.TestCase):
    def test_command_is_a_safe_encoded_powershell_invocation(self):
        command = backend.build_powershell_command()
        self.assertEqual(command[0], "powershell.exe")
        self.assertIn("-EncodedCommand", command)
        self.assertNotIn("-Command", command)
        # Nothing user-visible can break out of the argument list.
        self.assertTrue(all("QwenPaw" not in part for part in command[:-1]))

        script = base64.b64decode(command[-1]).decode("utf-16-le")
        self.assertIn(backend.APP_USER_MODEL_ID, script)
        self.assertIn("CreateToastNotifier", script)
        self.assertIn("QwenPaw has completed the turn.", script)
        self.assertIn("ToastNotificationManager", script)

    def test_single_quotes_are_doubled_inside_the_script(self):
        command = backend.build_powershell_command("it's", "it's done")
        script = base64.b64decode(command[-1]).decode("utf-16-le")
        self.assertIn("it&apos;s", script)


class PlatformTests(unittest.TestCase):
    def test_only_windows_is_supported(self):
        with patch.object(sys, "platform", "win32"):
            self.assertTrue(backend.notifications_supported())
        for platform in ("linux", "darwin"):
            with patch.object(sys, "platform", platform):
                self.assertFalse(backend.notifications_supported())

    def test_non_windows_turn_does_not_spawn_a_process(self):
        original = sys.platform
        sys.platform = "linux"
        try:
            with patch.object(
                asyncio, "create_subprocess_exec", new=AsyncMock()
            ) as spawn:
                self.assertFalse(asyncio.run(backend.show_toast()))
                spawn.assert_not_called()
        finally:
            sys.platform = original

    def test_windows_turn_spawns_a_hidden_toast(self):
        process = SimpleNamespace(
            returncode=0,
            communicate=AsyncMock(return_value=(b"", b"")),
        )
        original = sys.platform
        sys.platform = "win32"
        try:
            with patch.object(
                asyncio,
                "create_subprocess_exec",
                new=AsyncMock(return_value=process),
            ) as spawn:
                self.assertTrue(asyncio.run(backend.show_toast()))
                self.assertTrue(spawn.called)
                kwargs = spawn.call_args.kwargs
                self.assertEqual(kwargs["creationflags"], backend._CREATE_NO_WINDOW)
                self.assertEqual(kwargs["stderr"], asyncio.subprocess.PIPE)
        finally:
            sys.platform = original

    def test_failed_toast_never_raises(self):
        process = SimpleNamespace(
            returncode=1,
            communicate=AsyncMock(return_value=(b"", b"boom")),
        )
        original = sys.platform
        sys.platform = "win32"
        try:
            with patch.object(
                asyncio,
                "create_subprocess_exec",
                new=AsyncMock(return_value=process),
            ), self.assertLogs(backend.logger, level="WARNING"):
                self.assertFalse(asyncio.run(backend.show_toast()))

            with patch.object(
                asyncio,
                "create_subprocess_exec",
                new=AsyncMock(side_effect=OSError("no powershell")),
            ), self.assertLogs(backend.logger, level="WARNING"):
                self.assertFalse(asyncio.run(backend.show_toast()))
        finally:
            sys.platform = original


class ManifestTests(unittest.TestCase):
    def test_identity_and_windows_only_are_declared(self):
        self.assertEqual(MANIFEST["id"], "qwenpaw-console-turn-notifications")
        self.assertEqual(MANIFEST["author"], "BigBunnyBall大兔子球")
        self.assertEqual(set(MANIFEST["entry"]), {"backend"})
        self.assertEqual(MANIFEST["entry"]["backend"], "plugin.py")
        self.assertIn("Windows only", MANIFEST["description"])
        self.assertIn("仅支持 Windows", MANIFEST["description"])

    def test_no_browser_frontend_is_shipped(self):
        self.assertFalse((PLUGIN_DIR / "web").exists())
        self.assertFalse(any(PLUGIN_DIR.rglob("*.js")))

    def test_real_plugin_module_passes_qwenpaw_validation(self):
        from qwenpaw.plugins.validation import validate_plugin_module

        validate_plugin_module(MANIFEST["id"], PLUGIN_DIR, "plugin.py")


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
            "_http_router_registrations": list(
                self.registry._http_router_registrations
            ),
        }
        self.registry.unregister_plugin(MANIFEST["id"])
        self.registry._unregister_plugin_http_routes(MANIFEST["id"])
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

        api = PluginApi(MANIFEST["id"], {})
        api.set_registry(self.registry)
        return api

    def workspace(self):
        return SimpleNamespace(plugins=SimpleNamespace(hook_registry=HookRegistry()))

    def register(self):
        backend.TurnNotificationsPlugin().register(self.api())

    def test_repeated_workspace_reload_leaves_one_hook(self):
        self.register()
        workspace = self.workspace()
        for _ in range(3):
            for setup in self.registry.get_workspace_setup_hooks():
                setup.callback({"workspace": workspace})
            hooks = workspace.plugins.hook_registry.hooks_for(Phase.POST_RESPONSE)
            self.assertEqual(
                [hook.name for hook in hooks],
                [backend.COMPLETED_HOOK_NAME],
            )

    def test_old_and_renamed_hooks_are_both_removed(self):
        class LegacyHook(backend.LifecycleHook):
            phase = Phase.POST_RESPONSE
            name = "turn_notifications_completed"

        class UnrelatedHook(backend.LifecycleHook):
            phase = Phase.POST_RESPONSE
            name = "unrelated_hook"

        workspace = self.workspace()
        self.register()
        for setup in self.registry.get_workspace_setup_hooks():
            setup.callback({"workspace": workspace})
        workspace.plugins.hook_registry.register(LegacyHook())
        workspace.plugins.hook_registry.register(UnrelatedHook())
        self.registry.set_workspace_manager(
            SimpleNamespace(agents={"default": workspace})
        )

        removed = backend.remove_stale_runtime_hooks()
        self.assertEqual(removed, 2)
        self.assertEqual(
            [
                hook.name
                for hook in workspace.plugins.hook_registry.hooks_for(
                    Phase.POST_RESPONSE
                )
            ],
            ["unrelated_hook"],
        )

    def test_hook_shows_one_toast_for_a_console_turn(self):
        self.register()
        workspace = self.workspace()
        for setup in self.registry.get_workspace_setup_hooks():
            setup.callback({"workspace": workspace})
        hook = workspace.plugins.hook_registry.hooks_for(Phase.POST_RESPONSE)[0]
        with patch.object(backend, "show_toast", new=AsyncMock()) as toast:
            result = asyncio.run(hook.run(context()))
            toast.assert_awaited_once()
        self.assertIsInstance(result, HookResult)

    def test_hook_ignores_non_console_turns(self):
        self.register()
        workspace = self.workspace()
        for setup in self.registry.get_workspace_setup_hooks():
            setup.callback({"workspace": workspace})
        hook = workspace.plugins.hook_registry.hooks_for(Phase.POST_RESPONSE)[0]
        with patch.object(backend, "show_toast", new=AsyncMock()) as toast:
            asyncio.run(hook.run(context(channel="discord")))
            toast.assert_not_awaited()

    def test_failing_toast_cannot_fail_the_turn(self):
        self.register()
        workspace = self.workspace()
        for setup in self.registry.get_workspace_setup_hooks():
            setup.callback({"workspace": workspace})
        hook = workspace.plugins.hook_registry.hooks_for(Phase.POST_RESPONSE)[0]
        with patch.object(
            backend, "show_toast", new=AsyncMock(side_effect=RuntimeError("boom"))
        ), self.assertLogs(backend.logger, level="WARNING"):
            result = asyncio.run(hook.run(context()))
        self.assertIsInstance(result, HookResult)


if __name__ == "__main__":
    unittest.main()
