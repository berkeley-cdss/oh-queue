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
    "stub-jumbotron": !showJumbotron,
  });

  return (
    <div>
      <Navbar state={state} mode="party" />
      <OfflineIndicator offline={state.offline && state.loaded} />
      <div>
        {showJumbotron && <Jumbotron state={state} />}
        {!showJumbotron && <Messages messages={state.messages} />}
      </div>
      <div className={containerClass}>
        <div className="row">
          <PresenceIndicator state={state} hideWaitTime />
        </div>
        <div className="row">
          <div className="col-xs-12">
            <div className="card-holder">
              {state.groups
                .filter((group) => group.group_status === "active")
                .map((group) => (
                  <GroupCard group={group} state={state} />
                ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
