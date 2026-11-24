// A banner across the top of the page while the page can't reach the server. Screen
// readers announce it when it changes.
export function OfflineIndicator({ offline }) {
  return (
    <div className={`offline offline-${offline ? "down" : "up"}`} role="status">
      <div className="offline-content">
        {offline
          ? "Connection lost. Reconnecting..."
          : "Your computer is connected."}
      </div>
    </div>
  );
}
