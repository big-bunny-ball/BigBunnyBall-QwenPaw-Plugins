# v0.1.0 verification

Verified locally on 2026-10-30 against QwenPaw 2.2.2.post1 on Windows 11.

## Platform scope

**Version 1 supports Windows only.** On macOS and Linux `notifications_supported()` returns false and a completed turn is a silent no-op. This is a deliberate scope decision, stated in both `plugin.json` and the README.

## Passed

- QwenPaw's official `qwenpaw plugin validate qwenpaw-console-turn-notifications` command.
- Seventeen backend tests covering: fixed notification text, non-console/error filtering, XML escaping, quote-safe PowerShell encoding, Windows-only gating, hidden window flags, subprocess failure isolation, manifest identity, no frontend entry, and the real QwenPaw registry lifecycle.
- Repeated workspace reloads leave exactly one `POST_RESPONSE` hook. Cleanup removes both the current hook name and the pre-rename `turn_notifications_completed` name.
- The old plugin id `turn-notifications` was uninstalled and the new `qwenpaw-console-turn-notifications` installed. The live log shows one hook registration, no duplicate and no `hook ordering cycle detected`.
- `GET /api/turn-notifications/health` returns `platform_supported: true` with the fixed message.
- A real console turn was executed through `POST /api/console/chat` and completed with HTTP 200.

## Native toast proof

A visible native Windows toast was confirmed twice, not merely assumed:

1. Manual AUMID probe: a toast appeared in the bottom-right corner titled **QwenPaw** with the body **“QwenPaw has completed the turn.”**, captured to `tmp/review/` (git-ignored scratch space).
2. Plugin end-to-end: after the real console turn, the Windows notification database recorded `HKCU:\...\Notifications\Settings\QwenPaw.ConsoleTurnNotifications` with `LastNotificationAddedTime` decoding to `2026-10-30T22:43:24Z` — 12 seconds before the check, matching the test turn. The `AppUserModelId` key carries `DisplayName = QwenPaw`.

This is the decisive difference from the previous browser-based design, which only ever proved that a `Notification` object was constructed, never that anything appeared on screen.

## Why the previous version failed

The earlier browser implementation was reported as working when it was not. Its root cause chain:

- The Chrome profile had **no notification permission** recorded for the console origin (`content_settings.exceptions.notifications` was empty).
- With permission at `default`, constructing a browser `Notification` throws.
- That throw was swallowed by the reconnect `catch` in the stream loop, so the failure was completely silent.

The lesson carried into v1: verify the user-visible result, not the API call. The native design removes the permission layer entirely.

## Removed in this version

- `web/index.js` and the `frontend` manifest entry.
- The server-sent event stream and its subscriber store.
- All browser permission handling. No `Notification.requestPermission()` is called anywhere.
- The obsolete browser test harness, focus probe and live-browser script.

## Repository hygiene

- Every review screenshot is written to `tmp/review/`, and `tmp/` is in `.gitignore`.
- No image files are tracked by git in this repository. A stray committed screenshot from the first push was untracked with `git rm --cached`; the deletion is staged but **not committed**, since commits are the maintainer's call.

## Not claimed

- macOS or Linux support.
- Resilience to Windows Focus Assist, presentation mode or fullscreen-game suppression.
- Any behaviour when QwenPaw itself is not running.

No Git commit, tag, push or marketplace submission was made.
