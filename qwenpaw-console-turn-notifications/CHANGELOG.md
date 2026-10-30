# Changelog

All notable changes to Turn Notifications are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-30

### Added

- Invisible console listener with no plugin UI; enablement is controlled only from QwenPaw's plugin page.
- Console-turn completion detection using QwenPaw's supported `POST_RESPONSE` runtime hook.
- Fixed notification text: “QwenPaw has completed the turn.” No response previews or session labels.
- Authenticated, reconnectable server-sent events for live completion signals.
- Foreground suppression using the console tab's visibility and focus state.
- Safe backend and frontend hot-reload handling to avoid duplicate hooks and listeners.
- Backend and browser tests, including a real console-turn notification-delivery check.
- Deterministic, dependency-free v0.1.0 release packaging.

### Privacy

- No additional inference, telemetry, remote service or persistent response-content storage.
