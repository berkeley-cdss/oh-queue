export function timeoutPromise(ms, promise) {
  return new Promise((resolve, reject) => {
    const timeoutId = setTimeout(() => {
      reject(new Error("promise timeout"));
    }, ms);
    promise.then(
      (res) => {
        clearTimeout(timeoutId);
        resolve(res);
      },
      (err) => {
        clearTimeout(timeoutId);
        reject(err);
      },
    );
  });
}

export async function post(endpoint, data, skipTimeout) {
  const promise = fetch(endpoint, {
    method: "POST",
    cache: "no-cache",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  if (skipTimeout) {
    return promise;
  }
  return timeoutPromise(10000, promise).then((resp) => {
    // Refused (no longer enrolled in the course), gone (the course was
    // hidden) or unavailable (the database doesn't match the migrations): if
    // the page itself now fails too, reload it, so it shows the server's
    // explanation instead of seeming offline. Checking the page first means an
    // API error alone can't make the page reload over and over. Only the app's
    // own 503, which is JSON: Cloud Run answers 503 itself when no instance is
    // free, and that passes, so it's treated as offline until the next poll.
    const isJson = (resp.headers.get("Content-Type") || "").includes(
      "application/json",
    );
    if (
      resp.status === 403 ||
      resp.status === 404 ||
      (resp.status === 503 && isJson)
    ) {
      return fetch(window.location.href, { cache: "no-cache" }).then((page) => {
        if (!page.ok) {
          window.location.reload();
        }
        throw new Error(`${endpoint} answered ${resp.status}`);
      });
    }
    return resp.json();
  });
}

export class Socket {
  constructor() {
    setInterval(
      () => this.emit("connect", { url: window.location.href }),
      10000,
    );
    this.handlers = new Map();
    this.jobs = [];
    this.emit("connect", { url: window.location.href });
  }

  on(event, handler) {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, []);
    }
    this.handlers.get(event).push(handler);
  }

  trigger(event, args) {
    for (const handler of this.handlers.get(event) || []) {
      handler(args);
    }
  }

  removeAllListeners(eventType) {
    this.handlers.delete(eventType);
  }

  emit(...args) {
    const processQueue = () => {
      if (this.jobs.length > 0) {
        const args = this.jobs[0];
        this.actuallyEmit(...args)
          .finally(this.jobs.shift.bind(this.jobs))
          .then(processQueue);
      }
    };
    this.jobs.push(args);
    if (this.jobs.length === 1) {
      processQueue();
    }
  }

  actuallyEmit(event, params = {}, callback = null) {
    if (callback == null && typeof params === "function") {
      callback = params;
      params = {};
    }
    return post(`${window.basePath}/api/${event}`, params)
      .then(({ action, updates }) => {
        this.trigger("connect");
        for (const [event, payload] of updates) {
          this.trigger(event, payload);
        }
        if (callback != null) {
          callback(action);
        }
      })
      .catch((e) => {
        console.error(e);
        this.trigger("disconnect");
      });
  }
}
