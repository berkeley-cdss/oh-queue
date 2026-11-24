import { Link } from "react-router-dom";
import classNames from "classnames";
import { Trash } from "react-bootstrap-icons";
import Swal from "sweetalert2";
import { app } from "../app_instance";
import {
  getMyTicket,
  groupIsMine,
  isStaff,
  ticketQuestion,
  ticketTimeAgo,
} from "../state";

export function GroupCard({ group, state }) {
  const inGroup = groupIsMine(state, group);

  const cardClass = classNames("card", "group-card", {
    "border-primary": inGroup,
  });

  const ownerName = group.attendees[0].user.shortName;

  const joinText =
    group.attendees.length === 1
      ? `Join ${ownerName}!`
      : `Join ${ownerName} and ${group.attendees.length - 1} others!`;

  const joinGroup = () => {
    const join = () => app.makeRequest("join_group", group.id, true);
    const ticket = getMyTicket(state);
    if (ticket && ticket.group_id) {
      Swal.fire({
        title: "Are you sure?",
        text:
          "You have created a ticket for your previous group. If you switch groups," +
          " that ticket will be deleted",
        icon: "warning",
        showCancelButton: true,
        confirmButtonColor: "#3085d6",
        cancelButtonColor: "#d33",
        confirmButtonText: "Yes, do it!",
      }).then((result) => {
        if (result.value) {
          join();
        }
      });
    } else {
      join();
    }
  };

  const title = `${state.assignments[group.assignment_id].name} ${ticketQuestion(
    state,
    group,
  )} · ${state.locations[group.location_id].name}`;

  return (
    <div className={cardClass}>
      <div
        className={classNames("card-header d-flex align-items-center", {
          "text-bg-primary": inGroup,
        })}
      >
        <h2 className="h6 mb-0 me-auto">{title}</h2>
        {isStaff(state) && (
          <button
            type="button"
            className={classNames("btn btn-sm", {
              "btn-outline-secondary": !inGroup,
              "btn-outline-light": inGroup,
            })}
            aria-label={`Delete the group for ${title}`}
            title="Delete group"
            onClick={() => app.makeRequest("delete_group", group.id)}
          >
            <Trash aria-hidden="true" />
          </button>
        )}
      </div>
      <div className="card-body">
        {inGroup ? (
          <p>
            <b>You are in this group.</b>
          </p>
        ) : (
          <p>
            {state.currentUser ? ownerName : "A student"} is looking to
            collaborate!
          </p>
        )}
        {group.description ? (
          <blockquote className="blockquote fs-6">
            {group.description}
          </blockquote>
        ) : (
          <p>
            <i>No description</i>
          </p>
        )}
        <p>Created {ticketTimeAgo(group)}.</p>
        {state.currentUser &&
          (inGroup ? (
            <Link className="btn btn-primary" to={`/groups/${group.id}`}>
              Return to group
            </Link>
          ) : (
            <button
              className="btn btn-outline-primary"
              type="button"
              onClick={joinGroup}
            >
              {joinText}
            </button>
          ))}
      </div>
    </div>
  );
}
