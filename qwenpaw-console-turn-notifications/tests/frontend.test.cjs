"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const fs = require("node:fs");
const vm = require("node:vm");
const { MESSAGE, TurnNotifications } = require("../web/index.js");

function browser({ hidden = true, focused = false, permission = "granted" } = {}) {
  const notifications = [];
  class FakeNotification {
    static permission = permission;
    constructor(title, options) {
      this.title = title;
      this.options = options;
      notifications.push(this);
    }
    close() {}
  }
  const scope = {
    document: { hidden, hasFocus: () => scope.focused },
    Notification: FakeNotification,
    focused,
    focus() { this.focused = true; },
    AbortController,
    fetch: async () => { throw new Error("No test response configured"); },
    setTimeout,
    clearTimeout,
  };
  return { scope, notifications };
}

test("background completion shows exactly the requested fixed text", () => {
  const { scope, notifications } = browser();
  const listener = new TurnNotifications({ fetch: async () => {} }, scope);
  assert.equal(listener.notify(), true);
  assert.equal(notifications.length, 1);
  assert.equal(notifications[0].title, "QwenPaw");
  assert.equal(notifications[0].options.body, "QwenPaw has completed the turn.");
  assert.equal(MESSAGE, "QwenPaw has completed the turn.");
  assert.equal(JSON.stringify(notifications[0].options).includes("preview"), false);
  assert.equal(JSON.stringify(notifications[0].options).includes("session"), false);
});

test("foreground console does not show a redundant notification", () => {
  const { scope, notifications } = browser({ hidden: false, focused: true });
  const listener = new TurnNotifications({ fetch: async () => {} }, scope);
  assert.equal(listener.notify(), false);
  assert.equal(notifications.length, 0);
});

test("permission is read but never requested", () => {
  const { scope, notifications } = browser({ permission: "denied" });
  const listener = new TurnNotifications({ fetch: async () => {} }, scope);
  assert.equal(listener.notify(), false);
  assert.equal(notifications.length, 0);
});

test("stream parser accepts a completion split across network chunks", async () => {
  const { scope, notifications } = browser();
  const bytes = new TextEncoder();
  const chunks = [
    "event: stream.ready\ndata: {}\n\nevent: turn.comp",
    "leted\ndata: {}\n\n",
  ];
  const response = {
    ok: true,
    body: {
      getReader: () => ({
        read: async () => chunks.length
          ? { done: false, value: bytes.encode(chunks.shift()) }
          : { done: true },
      }),
    },
  };
  const requests = [];
  scope.fetch = async (url, options) => { requests.push({ url, options }); return response; };
  const listener = new TurnNotifications({
    getApiUrl: (path) => "http://localhost/api" + path,
    getApiToken: () => "test-token",
  }, scope);
  scope.setTimeout = (resolve) => { listener.stop(); resolve(); return 1; };
  listener.running = true;
  await listener.run();
  assert.equal(notifications.length, 1);
  assert.equal(notifications[0].options.body, MESSAGE);
  assert.equal(requests[0].url, "http://localhost/api/turn-notifications/events");
  assert.equal(requests[0].options.headers.Authorization, "Bearer test-token");
});

test("browser module evaluation does not use the Node module export", () => {
  const source = fs.readFileSync(require.resolve("../web/index.js"), "utf8");
  const window = {
    document: { hidden: true, hasFocus: () => false },
    QwenPaw: { host: {} },
    AbortController,
    setTimeout,
    clearTimeout,
  };
  vm.runInNewContext(source, { window, module: undefined, AbortController });
  assert.equal(typeof window.__qwenpawTurnNotifications, "object");
  window.__qwenpawTurnNotifications.stop();
});

test("unsupported browser fails quietly", () => {
  const { scope } = browser();
  delete scope.Notification;
  const listener = new TurnNotifications({ fetch: async () => {} }, scope);
  assert.equal(listener.notify(), false);
});
