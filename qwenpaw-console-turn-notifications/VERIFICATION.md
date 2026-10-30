# v0.1.0 verification

Verified locally on 2026-10-30 against QwenPaw 2.2.2.post1 on Windows 11.

## Passed

- QwenPaw's official `qwenpaw plugin validate qwenpaw-turn-system-notifications` command.
- Seven backend tests using the real QwenPaw plugin registry, supported `POST_RESPONSE` hook and authenticated event stream. They cover fixed-message completion, non-console/error filtering, repeated workspace reloads, stale-hook cleanup and subscriber cleanup.
- Six frontend tests covering the exact fixed text, foreground suppression, permission handling, split SSE chunks, authenticated URL/token helpers and browser blob-module evaluation.
- A real independent console turn completed successfully; the live plugin counter advanced from 0 to 1 without the previous hook-ordering error.
- An isolated real Chrome browser with notification permission granted loaded the shipped listener through QwenPaw's supported frontend reload hook. A real `POST /api/console/chat` turn advanced the counter from 3 to 4 and constructed the native notification with title `QwenPaw` and body exactly `QwenPaw has completed the turn.` There were no browser JavaScript errors.
- The browser listener uses the console Host SDK's actual `getApiUrl()` and `getApiToken()` helpers. QwenPaw's blob-module import path is covered by a regression test.
- Repeated frontend reloads stop the previous listener before starting a new one. The backend removes only its own stale runtime hooks.
- The plugin adds no console UI, React components, permission prompt or settings page. It never calls `Notification.requestPermission()`.
- No response text, session labels or completion history are collected or sent. There is no additional model inference or external service.
- Release ZIP contains `plugin.json` at its root, the Apache-2.0 licence and no tests, screenshots or caches.

## Scope correction

The initial implementation included response previews, session labels, replay history and unnecessary console controls. Those were removed. The only notification text is:

> QwenPaw has completed the turn.

Enable/disable is exclusively through QwenPaw's plugin page. Notification permission is managed in browser site settings and Windows settings.

## Display boundary

The live test verified the browser's native Notification API construction and delivery path. A visible Windows banner was not observed in the desktop capture, so Windows-level banner display is not claimed as verified. Browser notification permission and Windows notification settings, including Focus Assist / Do Not Disturb and fullscreen-game behaviour, still determine whether a banner is shown.

The isolated browser test used a controlled background visibility state because its automated Chrome window continued reporting itself as focused after minimisation. This is recorded explicitly; it does not establish that Windows displayed a banner.

No Git commit, tag, push or public release was made.
