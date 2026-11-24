import { Link, useParams } from "react-router-dom";
import moment from "moment";
import React from "react";
import { app } from "../app_instance";
import { Navbar } from "./navbar";
import { OfflineIndicator } from "./offline_indicator";
import { Pager } from "./pager";
import { Row } from "./row";
import { timeComparator } from "../state";

export function UserLayout({ state }) {
  const userID = +useParams().id;

  const [userData, setUserData] = React.useState({});
  const [isLoading, setIsLoading] = React.useState(false);
  const [page, setPage] = React.useState(0);

  if (app && !isLoading && Object.keys(userData).length === 0) {
    setIsLoading(true);
    app.makeRequest("get_user", userID, false, (userData) => {
      setUserData(userData);
    });
  }

  if (Object.keys(userData).length === 0) {
    return null;
  }

  const ticketRows = userData.tickets.map((ticket) => [
    moment.utc(ticket.created),
    <Row
      title={(ticket.user ? ticket.user.name : "Someone") + "'s Ticket"}
      link={`/tickets/${ticket.id}`}
      prop1={moment().to(moment.utc(ticket.created))}
      prop2={state.locations[ticket.location_id].name}
    />,
  ]);

  const rows = ticketRows
    .sort((a, b) => -timeComparator(a[0], b[0]))
    .map((x) => x[1]);

  return (
    <div>
      <Navbar state={state} mode="activity_log" />
      <OfflineIndicator offline={state.offline && state.loaded} />
      <main>
        <div className="hero">
          <div className="container">
            <h2>{userData.user.name}</h2>
            <p>{userData.user.email}</p>
            <div className="activity-buttons">
              <Link to="/activity_log" className="btn btn-warning">
                Back to list
              </Link>
            </div>
          </div>
        </div>
        <div className="container">
          <h3 className="h4">History</h3>
          <div>
            <div className="queue">
              {rows.slice(page * 50, (page + 1) * 50)}
            </div>
            <Pager page={page} setPage={setPage} pages={rows.length / 50} />
          </div>
        </div>
      </main>
    </div>
  );
}
