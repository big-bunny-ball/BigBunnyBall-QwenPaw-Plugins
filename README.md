# QwenPaw Plugins

Community plugins for [QwenPaw](https://qwenpaw.agentscope.io/), developed against its supported backend and console extension APIs. Each plugin lives in its own directory and has independent documentation, tests, versioning and releases.

面向 [QwenPaw](https://qwenpaw.agentscope.io/) 的社区插件，基于其官方支持的后端 API 与控制台扩展 API 开发。每个插件都位于独立目录中，拥有各自独立的文档、测试、版本号和发布流程。

## Plugins / 插件

| Directory / 目录 | Plugin ID | Version | Purpose / 用途 |
| --- | --- | --- | --- |
| [`qwenpaw-console-turn-notifications/`](qwenpaw-console-turn-notifications/) | `qwenpaw-console-turn-notifications` | `0.1.0` | Native **Windows** toast notifications for completed console turns. Windows only (v1).<br>控制台对话完成时显示原生 **Windows** 通知。仅支持 Windows（v1）。 |

The repository root contains shared licensing, ignore rules and release tooling. Plugin-specific implementation and instructions are in each plugin's README.

仓库根目录包含共享的许可证、忽略规则和发布工具。各插件的具体实现与使用说明请参阅该插件自身的 README。

## Local installation / 本地安装

```bat
qwenpaw plugin install <plugin-directory>
```

For example:

例如：

```bat
qwenpaw plugin install qwenpaw-console-turn-notifications
```

See the plugin's README for prerequisites, verification and uninstall steps. QwenPaw must remain running for backend hooks to operate. Browser-based plugins also require an open console tab; the current plugin does not, because it raises a native Windows toast.

前置条件、验证步骤和卸载方法请参阅插件自身的 README。后端钩子需要 QwenPaw 保持运行才能生效。基于浏览器的插件还需要保持一个控制台标签页处于打开状态；当前插件不需要，因为它直接调用原生 Windows 通知。

## Releases / 发布

Each plugin has its own semantic version in its `plugin.json` and `CHANGELOG.md`. A release uses a plugin-specific tag, for example `qwenpaw-console-turn-notifications-v0.1.0`.

每个插件在各自的 `plugin.json` 和 `CHANGELOG.md` 中维护独立的语义化版本号。发布时使用与插件对应的标签，例如 `qwenpaw-console-turn-notifications-v0.1.0`。

Build a plugin archive locally:

在本地构建插件归档：

```bat
python tools\package_plugin.py <plugin-directory>
```

The packager:

打包工具会：

- reads the plugin ID and version from `plugin.json`;
- 从 `plugin.json` 读取插件 ID 和版本号；
- writes `dist/<plugin-id>-v<version>.zip`;
- 输出 `dist/<plugin-id>-v<version>.zip`；
- places `plugin.json` at the ZIP root, without a containing directory;
- 将 `plugin.json` 放在 ZIP 根目录，不再套一层同名目录；
- includes only runtime files and plugin documentation/licensing, not tests or caches;
- 只包含运行时文件以及插件文档和许可证，不包含测试或缓存；
- uses fixed ZIP timestamps and permissions for deterministic output;
- 使用固定的 ZIP 时间戳和权限，以保证输出可复现；
- rejects unsafe paths, symlinks and archives over 10 MB; and
- 拒绝不安全的路径、符号链接以及超过 10 MB 的归档；并且
- prints a SHA-256 digest for reproducibility.
- 输出 SHA-256 摘要，便于校验复现。

Attach the plugin-specific ZIP to a release, not the monorepo's automatically generated **Source code** ZIP. The `dist/` directory is intentionally ignored by Git. Publishing, tagging, pushing and marketplace submission require a separate, explicit release decision.

发布时应附加该插件专属的 ZIP，而不是 GitHub 自动生成的 **Source code** 压缩包。`dist/` 目录已被 Git 有意忽略。发布、打标签、推送以及提交到插件市场，都需要单独且明确的发布决定。

## Development principles / 开发原则

- Use supported QwenPaw extension points; do not patch installed QwenPaw core files.
- 使用 QwenPaw 官方支持的扩展接入点；不要修改已安装的 QwenPaw 核心文件。
- Inspect the installed runtime API before relying on it and declare the tested version range.
- 在依赖某个运行时 API 之前先实际检查它，并声明已测试的版本范围。
- Prefer zero runtime dependencies and small, deterministic packages.
- 优先选择零运行时依赖，并保持包体小而可复现。
- Avoid telemetry and sensitive-data logging.
- 不要添加遥测，也不要记录敏感数据。
- Test locally before any public release.
- 任何公开发布之前都要先在本地完成测试。

## Licence / 许可证

Apache License 2.0. See [LICENSE](LICENSE).

Apache License 2.0，请参阅 [LICENSE](LICENSE)。
