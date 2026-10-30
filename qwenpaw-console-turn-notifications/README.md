# QwenPaw Console Turn Notifications

Show a native **Windows** toast when a **QwenPaw console turn completes**.

当 **QwenPaw 控制台中的一轮对话完成**时，显示原生 **Windows** 通知。

Version 1 supports **Windows only**. macOS and Linux are not supported and produce no notification.

v1 版本**仅支持 Windows**。macOS 和 Linux 暂不支持，也不会产生任何通知。

The notification text is always:

通知文本始终为：

> QwenPaw has completed the turn.

There is no browser notification, no permission prompt, no console UI, no settings page and no session label. Enabling and disabling the plugin is done exclusively on QwenPaw's plugin page.

不使用浏览器通知、不弹出权限请求、不添加控制台界面、不提供设置页面，也不显示会话标签。只能在 QwenPaw 的插件页面启用或停用此插件。

Because the toast is raised by Windows itself, it appears even when no console tab is open and even when the browser is closed.

由于通知由 Windows 系统自身发出，因此即使没有打开控制台标签页、甚至浏览器已关闭，通知依然会显示。

## Requirements / 使用要求

- Windows 10 or Windows 11.
- Windows 10 或 Windows 11。
- QwenPaw **2.2.2 or later in the 2.2.x series**; tested on **2.2.2.post1**.
- QwenPaw **2.2.x 系列中的 2.2.2 或更高版本**；已在 **2.2.2.post1** 上测试。
- Windows notifications enabled, and Focus Assist / Do Not Disturb in a state that allows banners.
- 已启用 Windows 通知，且专注助手或“勿扰”模式处于允许显示通知横幅的状态。

No Python dependency is installed and no network access is used.

不会安装额外的 Python 依赖，也不会使用网络访问。

## Install / 安装

From this monorepo checkout, run the following command:

在此 monorepo 的本地检出目录中，运行以下命令：

```bat
qwenpaw plugin install qwenpaw-console-turn-notifications
```

Alternatively, install the release ZIP:

也可以安装发布版 ZIP：

```bat
qwenpaw plugin install path\to\qwenpaw-console-turn-notifications-v0.1.0.zip
```

The ZIP has `plugin.json` at its root; do not unzip it into an additional nested directory.

ZIP 根目录中包含 `plugin.json`；解压后不要再额外套一层同名目录。

## Use / 使用方法

1. Enable **QwenPaw Console Turn Notifications** on the QwenPaw plugin page.
1. 在 QwenPaw 插件页面启用 **QwenPaw Console Turn Notifications**。

2. Complete a turn in the QwenPaw console.
2. 在 QwenPaw 控制台中完成一轮对话。

3. A Windows toast appears in the bottom-right corner with the title **QwenPaw** and the text **“QwenPaw has completed the turn.”**
3. Windows 右下角会弹出一条通知，标题为 **QwenPaw**，正文为 **“QwenPaw has completed the turn.”**。

If no toast appears, check Windows **Settings → System → Notifications**, confirm notifications are on and Focus Assist is not silencing them, then complete another turn.

如果没有看到通知，请检查 Windows 的**设置 → 系统 → 通知**，确认通知已开启且专注助手未将其静音，然后再次完成一轮对话。

## Behaviour and limits / 行为与限制

The plugin uses QwenPaw's `POST_RESPONSE` lifecycle hook. Only successful console turns notify; other channels and turns that ended with an error stay silent.

插件使用 QwenPaw 的 `POST_RESPONSE` 生命周期钩子。只有成功完成的控制台对话才会通知；其他渠道以及以错误结束的对话不会通知。

Each completed turn shows one toast. The toast is raised through Windows WinRT using a dedicated application identity, so it is labelled **QwenPaw** rather than another program.

每完成一轮对话会显示一条通知。通知通过 Windows WinRT 以专属应用标识发出，因此显示为 **QwenPaw**，而不是其他程序的名称。

No response text is read, stored or transmitted. The plugin never inspects the reply, only that a turn finished successfully.

不会读取、保存或传输回复正文。插件不会检查回复内容，只判断一轮对话是否成功结束。

Toast display ultimately depends on Windows notification settings. Presentation mode, Focus Assist, fullscreen games and notification volume can suppress banners.

通知是否显示最终取决于 Windows 的通知设置。演示模式、专注助手、全屏游戏和通知数量限制都可能抑制横幅显示。

## Development / 开发

No additional runtime dependencies or build step are needed.

无需额外的运行时依赖或构建步骤。

From the monorepo root, run the following checks:

在 monorepo 根目录运行以下检查：

```bat
"%USERPROFILE%\.qwenpaw\venv\Scripts\python.exe" -m unittest discover -s qwenpaw-console-turn-notifications/tests -p "test_*.py" -v
qwenpaw plugin validate qwenpaw-console-turn-notifications
```

Build the deterministic release archive with the following command:

使用以下命令构建可复现的发布归档：

```bat
python tools\package_plugin.py qwenpaw-console-turn-notifications
```

The archive is written to `dist/qwenpaw-console-turn-notifications-v0.1.0.zip`, contains `plugin.json` at its root, excludes development files and is checked against the 10 MB limit.

归档将生成至 `dist/qwenpaw-console-turn-notifications-v0.1.0.zip`，根目录包含 `plugin.json`，不包含开发文件，并会检查是否超过 10 MB 限制。

## Uninstall / 卸载

Run the following command to uninstall the plugin:

运行以下命令卸载插件：

```bat
qwenpaw plugin uninstall qwenpaw-console-turn-notifications
```

Uninstalling does not change any Windows notification setting.

卸载不会更改任何 Windows 通知设置。

## Licence / 许可证

Apache-2.0. See the repository-level [LICENSE](../LICENSE).

Apache-2.0。请参阅仓库根目录的 [LICENSE](../LICENSE)。
