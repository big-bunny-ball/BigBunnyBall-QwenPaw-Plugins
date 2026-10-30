"""Manual/local end-to-end verification; not part of the release archive."""
from __future__ import annotations

import asyncio
import json
import time
import os
from pathlib import Path

import win32gui
import win32process

from playwright.async_api import async_playwright
from qwenpaw.cli.plugin_commands import _get_api_base
from qwenpaw.utils.runtime_api import api_client

ROOT = Path(__file__).resolve().parents[1]


async def main() -> None:
    client = api_client(_get_api_base(), timeout=5)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            channel="chrome",
            headless=False,
        )
        context = await browser.new_context(
            permissions=["notifications"],
        )
        page = await context.new_page()
        console_errors = []
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        await page.add_init_script(
            """window.__turnNotifications = [];
            const NativeNotification = window.Notification;
            window.__NativeNotification = NativeNotification;
            window.Notification = class extends NativeNotification {
              constructor(title, options) {
                super(title, options);
                window.__turnNotifications.push({title, body: options.body});
              }
            };"""
        )
        await page.goto("http://127.0.0.1:8088")
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_function("Boolean(window.QwenPaw && window.QwenPaw.host)", timeout=30000)
        # This local console has auth disabled. Do not read credentials.
        token = ""
        assert await page.evaluate("typeof QwenPaw.host.getApiToken === 'function'")
        cdp = await context.new_cdp_session(page)
        browser_cdp = await browser.new_browser_cdp_session()
        system_info = await browser_cdp.send("SystemInfo.getProcessInfo")
        browser_pids = {
            item["id"] for item in system_info["processInfo"]
            if item["type"] == "browser"
        }
        candidates = []
        def collect_windows(handle, _):
            _, pid = win32process.GetWindowThreadProcessId(handle)
            if pid in browser_pids and win32gui.IsWindowVisible(handle):
                candidates.append(handle)
        await asyncio.to_thread(win32gui.EnumWindows, collect_windows, None)
        assert len(candidates) == 1, candidates
        hwnd = candidates[0]
        await asyncio.to_thread(win32gui.ShowWindow, hwnd, 6)  # SW_MINIMIZE
        await page.wait_for_timeout(750)
        background_state = await page.evaluate(
            "({hidden:document.hidden, focused:document.hasFocus()})"
        )
        print("Background state:", background_state, flush=True)
        # Automated Chrome windows can keep visibility/focus pinned when
        # minimised. Use the browser's visibility transition for this test;
        # the shipped listener itself reads the real browser properties.
        await page.evaluate(
            """() => {
              Object.defineProperty(document, 'hidden', {configurable:true, get:() => true});
              Object.defineProperty(document, 'hasFocus', {configurable:true, value:() => false});
              document.dispatchEvent(new Event('visibilitychange'));
            }"""
        )
        assert await page.evaluate("document.hidden")
        result = await page.evaluate(
            """async () => {
              const { a9: reload } = await import('/assets/index-BpFaGbCq.js');
              await reload('turn-notifications');
              return {
                permission: Notification.permission,
                apiUrl: QwenPaw.host.getApiUrl('/turn-notifications/events'),
                listener: Boolean(window.__qwenpawTurnNotifications),
              };
            }"""
        )
        print("Listener:", json.dumps(result), flush=True)
        await page.wait_for_timeout(1000)
        before = client.get("turn-notifications/health").json()
        print("Health before:", before, flush=True)
        # The console window is genuinely minimised, not merely another tab.
        response = client.post(
            "console/chat",
            params={"agent_id": "default"},
            json={"input": [{"role": "user", "content": [
                {"type": "text", "text": "Reply only: OK. Do not use tools."},
            ]}]},
            headers={"Authorization": f"Bearer {token}"} if token else {},
            timeout=90,
        )
        print("Test turn HTTP:", response.status_code, flush=True)
        response.raise_for_status()
        await page.wait_for_timeout(2000)
        after = client.get("turn-notifications/health").json()
        notifications = await page.evaluate("window.__turnNotifications")
        stream = await page.evaluate(
            "({ running: window.__qwenpawTurnNotifications?.running, "
            "hidden: document.hidden, focused: document.hasFocus() })"
        )
        outcome = {
            "health_before": before,
            "health_after": after,
            "notifications": notifications,
            "listener": stream,
            "console_errors": console_errors,
        }
        print("RESULT:", json.dumps(outcome, indent=2), flush=True)
        (ROOT / "tests" / "live-browser-result.json").write_text(
            json.dumps(outcome, indent=2), encoding="utf-8"
        )
        assert after["latest_sequence"] == before["latest_sequence"] + 1
        assert notifications == [
            {"title": "QwenPaw", "body": "QwenPaw has completed the turn."}
        ]
        assert not console_errors
        await page.screenshot(path=str(ROOT / "tests" / "live-notification-page.png"))
        await cdp.send("Browser.setWindowBounds", {
            "windowId": (await cdp.send("Browser.getWindowForTarget"))["windowId"],
            "bounds": {"windowState": "normal"},
        })
        await page.wait_for_timeout(250)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
