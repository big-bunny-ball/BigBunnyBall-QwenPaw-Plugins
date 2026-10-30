# Changelog

## 0.1.0

- Native Windows toast notifications for completed QwenPaw console turns.
- Declared as `"type": "hook"` (Lifecycle Hook). It runs QwenPaw lifecycle hooks and does not register tools, providers, commands, channels, memory backends, frontend bundles or an App, so `general` — the fallback category — was wrong.
- Fixed notification text: “QwenPaw has completed the turn.”
- Windows-only support in v1; macOS and Linux are no-ops.
- Browser notifications, the frontend entry, the event stream and all console UI were removed. The toast is raised by Windows itself, so it works with the browser closed.
- No response text is read, stored or transmitted.
- Safe backend hot-reload handling, including cleanup of the pre-rename hook name.

### Fixed during 0.1.0 development

- Removed a global shutdown cleanup hook. It stripped the `POST_RESPONSE` hook from every live workspace when a workspace instance was stopped, leaving later turns silent. Cleanup now runs only at startup and for a newly created workspace.
- **Removed a self-inflicted duplicate hook that caused `HookCycleError`.** The plugin's priority-64 startup cleanup called `ensure_hook_installed()`, then QwenPaw's `register_runtime_hook` installed the same hook from its own priority-65 startup callback. Two identically named hooks make `_topo_sort` collapse `{h.name: h}` while still comparing against the full list length, so the next turn failed with `hook ordering cycle detected; unresolved: ['qwenpaw_console_turn_notification']`. The startup callback now only removes.
- `ensure_hook_installed()` is manual repair only. It collapses duplicates to one before adding, so it can never multiply hooks.
- Diagnostics read `_by_phase` directly instead of `hooks_for()`, which raises during sorting and would have hidden the very duplicate being investigated.
- `/health` reports `hook_counts` (anything above 1 means a cycle is imminent) plus in-memory counters (`hook_runs`, `attempts`, `successes`, `failures`, `last_channel`, `last_error`).
