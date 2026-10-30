# Turn Notifications

Show a native system notification when a **QwenPaw console turn completes**.

当 **QwenPaw 控制台中的一轮对话完成**时，显示原生系统通知。

The notification body is always:

通知正文始终为：

> QwenPaw has completed the turn.

There is no response preview, session label, plugin settings page, console button or permission prompt. Enabling and disabling the plugin is done exclusively on QwenPaw's plugin page. No additional model inference or remote service is used.

不包含回复预览、会话标签、插件设置页面、控制台按钮或权限请求弹窗。只能在 QwenPaw 的插件页面启用或停用此插件。不会进行额外的模型推理，也不会使用远程服务。

## Requirements / 使用要求

- QwenPaw **2.2.2 or later in the 2.2.x series**; tested on **2.2.2.post1**.
- QwenPaw **2.2.x 系列中的 2.2.2 或更高版本**；已在 **2.2.2.post1** 上测试。
- A desktop browser with Notification API support.
- 支持 Notification API 的桌面浏览器。
- At least one QwenPaw console tab left open. A closed browser cannot receive completion signals.
- 至少保留一个打开的 QwenPaw 控制台标签页。浏览器关闭后无法接收完成信号。
- Notification permission granted to the QwenPaw console origin in the browser's site settings.
- 在浏览器的网站设置中，允许 QwenPaw 控制台来源发送通知。
- On Windows, notifications enabled for the browser in **Settings → System → Notifications**. Focus Assist / Do Not Disturb may hide banners.
- 在 Windows 的**设置 → 系统 → 通知**中为浏览器启用通知。专注助手或“勿扰”模式可能会隐藏通知横幅。

## Install / 安装

From this monorepo checkout, run the following command:

在此 monorepo 的本地检出目录中，运行以下命令：

```bat
qwenpaw plugin install qwenpaw-console-turn-notifications
```

Alternatively, install the release ZIP:

也可以安装发布版 ZIP：

```bat
qwenpaw plugin install path\to\turn-notifications-v0.1.0.zip
```

Reload the console after installation. The ZIP has `plugin.json` at its root; do not unzip it into an additional nested directory.

安装后重新加载控制台。ZIP 根目录中包含 `plugin.json`；解压后不要再额外套一层同名目录。

## Use / 使用方法

1. Enable **Turn Notifications** on the QwenPaw plugin page.
1. 在 QwenPaw 插件页面启用 **Turn Notifications**。

2. Open or reload the console and log in normally.
2. 打开或重新加载控制台，并正常登录。

3. Allow notifications for the console origin in the browser's site settings. The plugin never requests permission itself.
3. 在浏览器的网站设置中允许控制台来源发送通知。插件本身不会主动请求权限。

4. Complete a turn while the console is in the background or another application is focused. The browser displays **“QwenPaw has completed the turn.”**
4. 在控制台位于后台或焦点位于其他应用时完成一轮对话。浏览器会显示 **“QwenPaw has completed the turn.”**。

5. Click the notification to focus the console.
5. 点击通知即可将焦点切换到控制台。

If no notification appears, check the console origin's notification permission and Windows notification settings, including Focus Assist / Do Not Disturb. Then reload the console and complete another turn.

如果没有显示通知，请检查控制台来源的通知权限以及 Windows 通知设置，包括专注助手或“勿扰”模式。然后重新加载控制台，再完成一轮对话。

## Behaviour and limits / 行为与限制

The plugin uses QwenPaw's `POST_RESPONSE` lifecycle hook for successful console turns. Non-console channels and turns with an error do not notify.

插件使用 QwenPaw 的 `POST_RESPONSE` 生命周期钩子检测成功完成的控制台对话。非控制台渠道和发生错误的对话不会触发通知。

The frontend uses the console Host SDK's `getApiUrl()` and `getApiToken()` helpers to consume the authenticated `/api/turn-notifications/events` server-sent event stream.

前端使用控制台 Host SDK 的 `getApiUrl()` 和 `getApiToken()` 辅助方法，接收经过身份验证的 `/api/turn-notifications/events` 服务器发送事件流。

A notification is shown only when the console tab is hidden or unfocused. It is suppressed while that tab is visible and focused.

仅在控制台标签页隐藏或失去焦点时显示通知。当该标签页可见且处于焦点状态时，不显示通知。

Multiple open console tabs may each display the same completion. This simple version does not coordinate claims across tabs.

多个打开的控制台标签页可能分别显示同一完成通知。此简化版本不会在标签页之间协调通知归属。

The listener reconnects after a dropped stream. Events missed while disconnected are not replayed.

事件流断开后，监听器会自动重新连接。断开期间错过的事件不会重播。

No response text is read, collected or sent to the browser. No completion history or response content is persisted.

不会读取、收集或向浏览器发送回复正文。不会持久化保存完成历史或回复内容。

Browser and Windows policies ultimately control banner display. Sleep, browser suspension or closing the console can prevent delivery.

通知横幅最终由浏览器和 Windows 的策略控制。系统睡眠、浏览器挂起或关闭控制台都可能导致通知无法送达。

## Development / 开发

No additional runtime dependencies or build step are needed.

无需额外的运行时依赖或构建步骤。

From the monorepo root, run the following checks:

在 monorepo 根目录运行以下检查：

```bat
"%USERPROFILE%\.qwenpaw\venv\Scripts\python.exe" -m unittest discover -s qwenpaw-console-turn-notifications/tests -p "test_*.py" -v
node --test qwenpaw-console-turn-notifications/tests/frontend.test.cjs
node --check qwenpaw-console-turn-notifications/web/index.js
qwenpaw plugin validate qwenpaw-console-turn-notifications
```

Build the deterministic release archive with the following command:

使用以下命令构建可复现的发布归档：

```bat
python tools\package_plugin.py qwenpaw-console-turn-notifications
```

The archive is written to `dist/turn-notifications-v0.1.0.zip`, contains `plugin.json` at its root, excludes development files and is checked against the 10 MB limit.

归档将生成至 `dist/turn-notifications-v0.1.0.zip`，根目录包含 `plugin.json`，不包含开发文件，并会检查是否超过 10 MB 限制。

## Uninstall / 卸载

Run the following command to uninstall the plugin:

运行以下命令卸载插件：

```bat
qwenpaw plugin uninstall turn-notifications
```

Reload open console tabs afterwards. Uninstalling does not change browser or Windows notification settings.

卸载后重新加载已打开的控制台标签页。卸载不会更改浏览器或 Windows 的通知设置。

## Licence / 许可证

Apache-2.0. See the repository-level [LICENSE](../LICENSE).

Apache-2.0。请参阅仓库根目录的 [LICENSE](../LICENSE)。
