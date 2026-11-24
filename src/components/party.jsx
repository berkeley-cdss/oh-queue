import classNames from "classnames";
import { requestNotificationPermission } from "../common";
import { GroupCard } from "./group_card";
import { Jumbotron } from "./jumbotron";
import { Messages } from "./messages";
import { Navbar } from "./navbar";
import { OfflineIndicator } from "./offline_indicator";
import { PresenceIndicator } from "./presence_indicator";
import { getMyGroup, getMyTicket, isStaff } from "../state";

export let Party = ({ state }) => {
  if (isStaff(state) || getMyTicket(state)) {
    requestNotificationPermission();
  }

  if (!state.loaded) return null;

  const showJumbotron = !getMyGroup(state);

  let containerClass = classNames({
    container: true,
    "mt-4": !showJumbotron,
  });

  return (
    <div>
      <Navbar state={state} mode="party" />
      <OfflineIndicator offline={state.offline && state.loaded} />
      <main>
        <div>
          {showJumbotron && <Jumbotron state={state} />}
          {!showJumbotron && (
            <div className="container mt-3">
              <Messages messages={state.messages} />
            </div>
          )}
        </div>
        <div className={containerClass}>
          <PresenceIndicator state={state} hideWaitTime />
          <div className="card-holder">
            {state.groups
              .filter((group) => group.group_status === "active")
              .map((group) => (
                <GroupCard key={group.id} group={group} state={state} />
              ))}
          </div>
        </div>
      </main>
    </div>
  );
};
