/* QwenPaw Turn Notifications — fixed-text, dependency-free browser listener. */
(function (root, factory) {
  const api = factory();
  if (
    typeof window === "undefined" &&
    typeof module === "object" &&
    module.exports
  ) {
    module.exports = api;
  }
  if (root && root.QwenPaw && root.QwenPaw.host && root.document) {
    api.start(root.QwenPaw.host, root);
  }
})(typeof window !== "undefined" ? window : globalThis, function () {
  "use strict";

  const MESSAGE = "QwenPaw has completed the turn.";

  class TurnNotifications {
    constructor(host, scope) {
      this.host = host;
      this.scope = scope;
      this.abort = null;
      this.timer = null;
      this.running = false;
    }

    notify() {
      if (this.scope.document.hidden === false && this.scope.document.hasFocus()) {
        return false;
      }
      const Notification = this.scope.Notification;
      if (!Notification || Notification.permission !== "granted") return false;
      const notification = new Notification("QwenPaw", {
        body: MESSAGE,
        icon: "/qwenpaw-symbol.svg",
      });
      notification.onclick = () => {
        this.scope.focus();
        notification.close();
      };
      return true;
    }

    start() {
      if (this.running) return;
      this.running = true;
      this.connect();
    }

    stop() {
      this.running = false;
      if (this.abort) this.abort.abort();
      if (this.timer !== null) this.scope.clearTimeout(this.timer);
    }

    connect() {
      if (this._connecting) return this._connecting;
      this._connecting = this.run().finally(() => { this._connecting = null; });
      return this._connecting;
    }

    async run() {
      while (this.running) {
        this.abort = new this.scope.AbortController();
        try {
          const token = this.host.getApiToken();
          const response = await this.scope.fetch(
            this.host.getApiUrl("/turn-notifications/events"),
            {
              headers: {
                Accept: "text/event-stream",
                ...(token ? { Authorization: "Bearer " + token } : {}),
              },
              cache: "no-store",
              signal: this.abort.signal,
            },
          );
          if (!response.ok || !response.body) throw new Error("Stream unavailable");
          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";
          while (this.running) {
            const part = await reader.read();
            if (part.done) break;
            buffer += decoder.decode(part.value, { stream: true });
            buffer = buffer.replace(/\r\n/g, "\n");
            let boundary;
            while ((boundary = buffer.indexOf("\n\n")) !== -1) {
              const block = buffer.slice(0, boundary);
              buffer = buffer.slice(boundary + 2);
              if (block.split("\n").some((line) => line === "event: turn.completed")) {
                this.notify();
              }
            }
          }
        } catch (error) {
          if (!this.running || (error && error.name === "AbortError")) return;
        }
        if (!this.running) return;
        await new Promise((resolve) => {
          this.timer = this.scope.setTimeout(resolve, 3000);
        });
      }
    }
  }

  function start(host, scope) {
    // QwenPaw can reload a frontend plugin without reloading the page.
    if (scope.__qwenpawTurnNotifications) {
      scope.__qwenpawTurnNotifications.stop();
    }
    const listener = new TurnNotifications(host, scope);
    scope.__qwenpawTurnNotifications = listener;
    listener.start();
    return listener;
  }

  return { MESSAGE, TurnNotifications, start };
});
