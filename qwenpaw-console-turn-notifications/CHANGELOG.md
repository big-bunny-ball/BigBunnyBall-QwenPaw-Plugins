# Changelog

## 0.1.0

- Native Windows toast notifications for completed QwenPaw console turns.
- Fixed notification text: “QwenPaw has completed the turn.”
- Windows-only support in v1; macOS and Linux are no-ops.
- Browser notifications, the frontend entry, the event stream and all console UI were removed. The toast is raised by Windows itself, so it works with the browser closed.
- No response text is read, stored or transmitted.
- Safe backend hot-reload handling, including cleanup of the pre-rename hook name.
