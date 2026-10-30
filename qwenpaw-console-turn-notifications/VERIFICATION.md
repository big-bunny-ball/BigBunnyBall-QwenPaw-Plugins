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

## Silent-failure investigation (resolved)

After the first working toast, later turns produced nothing. The Windows `LastNotificationAddedTime` stayed pinned at `22:43:24Z`, proving the toast never fired rather than being displayed and missed.

Evidence gathered:

- The plugin was enabled and its hook was registered in the log at `22:43:08`.
- No warning, error or traceback appeared in `qwenpaw.log`.
- Plugin `logger` output does not reach `qwenpaw.log`, so the absence of warnings proved nothing — a design weakness now addressed by the `/health` counters.

Timeline that identified the cause:

| Time | Event |
| --- | --- |
| 22:43:08 | Plugin installed; zero-downtime workspace reload begins |
| 22:43:24 | Test turn → toast delivered ✓ |
| 22:44:30 | `Old workspace instance stopped: default. Delayed cleanup completed.` |
| 22:45:36 | Next turn → no toast, timestamp unchanged ✗ |

The regression test `test_no_global_shutdown_hook_is_registered` encodes the cause: the plugin registered a **global shutdown cleanup** that removed its hook from *every* live workspace. When the replaced workspace instance finished its delayed cleanup, the running workspace lost its `POST_RESPONSE` hook and nothing re-added it. Startup-only cleanup plus `ensure_hook_installed()` removes the failure mode; both are covered by tests.

## Post-fix verification

- `GET /api/turn-notifications/health` reports `hook_counts: {"default": 1}`.
- Two consecutive real console turns each produced `hook_runs: 2, attempts: 2, successes: 2, failures: 0` with `last_channel: "console"`.
- `LastNotificationAddedTime` advanced on both turns (`…40150560865` → `…40337220697`), matching `last_success_at` to the second.
- Nineteen tests pass, including the shutdown-hook regression and hook-restoration tests.

## Duplicate-hook cycle (resolved)

A turn later failed with:

```
UNKNOWN_AGENT_ERROR
hook ordering cycle detected; unresolved: ['qwenpaw_console_turn_notification']
```

Cause, confirmed at `qwenpaw/runtime/hooks.py:180` and `:248`:

- `_topo_sort` builds `name_to_hook = {h.name: h for h in hooks}`, so two hooks sharing a name collapse into one dict entry.
- It then compares `len(result) != len(hooks)` against the full list, which still counts both.
- The mismatch raises `HookCycleError`. Identical names therefore *always* fail, regardless of dependencies.

The duplicate was self-inflicted by the previous fix: the plugin registered a **priority-64** startup cleanup that called `ensure_hook_installed()`, while QwenPaw's `register_runtime_hook` installs the same hook from a **priority-65** startup callback (`plugins/api.py`). Priority 64 added one hook, priority 65 added a second.

Fixes and their regression tests:

| Change | Test |
| --- | --- |
| Startup callback only removes; it never installs | `test_startup_sequence_registers_exactly_one_hook` |
| `ensure_hook_installed()` collapses duplicates before adding | `test_duplicate_hooks_are_collapsed_not_multiplied` |
| Diagnostics read `_by_phase`, bypassing the sorting call | exercised by the duplicate test, which would otherwise raise |
| No global shutdown hook | `test_no_global_shutdown_hook_is_registered` |

Live confirmation after reinstall: `hook_counts: {"default": 1}`; two further turns produced `hook_runs: 2, successes: 2, hook_counts` still `1`; no `hook ordering cycle` entries logged after the fix.



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
