import { requestNotificationPermission } from "../common";
import { Navbar } from "./navbar";
import { OfflineIndicator } from "./offline_indicator";
import { Queue } from "./queue";
import { getMyTicket, isStaff } from "../state";

export let Home = ({ state }) => {
  if (isStaff(state) || getMyTicket(state)) {
    requestNotificationPermission();
  }

  // TODO loading indicator instead of blank screen
  if (!state.loaded) return null;

  return (
    <div>
      <Navbar state={state} mode="queue" />
      <OfflineIndicator offline={state.offline && state.loaded} />
      <main>
        <Queue state={state} />
      </main>
    </div>
  );
};
