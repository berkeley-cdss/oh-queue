import { isStaff } from "./state";

// Shown notifications, by tag, so they can be closed.
const notifications = new Map();

export function requestNotificationPermission() {
  if ("Notification" in window && Notification.permission === "default") {
    Notification.requestPermission().catch(() => {});
  }
}

export function notifyUser(title, body, tag) {
  if (!("Notification" in window) || Notification.permission !== "granted") {
    return;
  }
  try {
    const notification = new Notification(title, {
      body,
      icon: window.location.origin + "/static/img/logo-tiny.png",
      tag,
    });
    notification.onclick = () => {
      window.focus();
      notification.close();
    };
    notification.onclose = () => {
      if (notifications.get(tag) === notification) {
        notifications.delete(tag);
      }
    };
    notifications.set(tag, notification);
  } catch {
    // Some browsers, such as Chrome on Android, only show notifications from a service worker.
  }
}

// Plays audio file when new ticket is created on instructor device
export function playNewTicketSound() {
  const newTicketSound = new Audio("/static/img/ding.mp3");
  newTicketSound.currentTime = 0;
  newTicketSound.play().catch(() => {});
}

export function cancelNotification(tag) {
  const notification = notifications.get(tag);
  if (notification) {
    notification.close();
    notifications.delete(tag);
  }
}

// Signs in, then comes back to this page.
export function loginPath() {
  const here = window.location.pathname + window.location.search;
  return "/login/?next=" + encodeURIComponent(here);
}

export function isPartyRoot(state) {
  return (
    state.config.party_enabled &&
    (!JSON.parse(state.config.is_queue_open) || !isStaff(state))
  );
}
