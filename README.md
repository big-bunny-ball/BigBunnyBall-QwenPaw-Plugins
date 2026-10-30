# QwenPaw Plugins

Community plugins for [QwenPaw](https://qwenpaw.agentscope.io/), developed against its supported backend and console extension APIs. Each plugin lives in its own directory and has independent documentation, tests, versioning and releases.

## Plugins

| Directory | Plugin ID | Version | Purpose |
| --- | --- | --- | --- |
| [`qwenpaw-console-turn-notifications/`](qwenpaw-console-turn-notifications/) | `turn-notifications` | `0.1.0` | Native system notifications for completed console turns when the console is hidden or unfocused. |

The repository root contains shared licensing, ignore rules and release tooling. Plugin-specific implementation and instructions are in each plugin's README.

## Local installation

```bat
qwenpaw plugin install <plugin-directory>
```

For example:

```bat
qwenpaw plugin install qwenpaw-console-turn-notifications
```

See the plugin's README for prerequisites, verification and uninstall steps. QwenPaw must remain running for backend hooks to operate; browser-based plugins also require an open console tab.

## Releases

Each plugin has its own semantic version in its `plugin.json` and `CHANGELOG.md`. A release uses a plugin-specific tag, for example `turn-notifications-v0.1.0`.

Build a plugin archive locally:

```bat
python tools\package_plugin.py <plugin-directory>
```

The packager:

- reads the plugin ID and version from `plugin.json`;
- writes `dist/<plugin-id>-v<version>.zip`;
- places `plugin.json` at the ZIP root, without a containing directory;
- includes only runtime files and plugin documentation/licensing, not tests or caches;
- uses fixed ZIP timestamps and permissions for deterministic output;
- rejects unsafe paths, symlinks and archives over 10 MB; and
- prints a SHA-256 digest for reproducibility.

Attach the plugin-specific ZIP to a release, not the monorepo's automatically generated **Source code** ZIP. The `dist/` directory is intentionally ignored by Git. Publishing, tagging, pushing and marketplace submission require a separate, explicit release decision.

## Development principles

- Use supported QwenPaw extension points; do not patch installed QwenPaw core files.
- Inspect the installed runtime API before relying on it and declare the tested version range.
- Prefer zero runtime dependencies and small, deterministic packages.
- Avoid telemetry and sensitive-data logging.
- Test locally before any public release.

## Licence

Apache License 2.0. See [LICENSE](LICENSE).
