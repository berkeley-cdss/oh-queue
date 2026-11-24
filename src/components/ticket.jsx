import { Link } from "react-router-dom";
import classNames from "classnames";
import moment from "moment";
import { app } from "../app_instance";
import {
  isStaff,
  isTicketHelper,
  ticketAssignment,
  ticketDisplayTime,
  ticketIsMine,
  ticketLocation,
  ticketPosition,
  ticketQuestion,
  ticketStatus,
  ticketTimeAgo,
  ticketTimeSinceAssigned,
} from "../state";

export let Ticket = ({ state, ticket, independent }) => {
  let assignment = ticketAssignment(app.state, ticket);
  let location = ticketLocation(app.state, ticket);

  const staff = isStaff(state);

  const staffName = ticket.helper
    ? isTicketHelper(state, ticket)
      ? "you"
      : ticket.helper.name
    : "someone";
  // Only staff, and the ticket's own student or group, get the student's
  // details; everyone else sees "a student".
  const studentName = ticket.user
    ? ticketIsMine(state, ticket)
      ? "you"
      : staff
        ? ticket.user.name
        : "a student"
    : "a student";

  const capitalize = (x) => x[0].toUpperCase() + x.slice(1);
  const possessive = (x) => (x === "you" ? "your" : x + "'s");

  var status;
  if (ticket.status === "pending") {
    status = ticketDisplayTime(ticket) + " in " + location.name;
  } else if (ticket.status === "juggled") {
    status = `${capitalize(staffName)} put ${studentName} on hold ${moment
      .utc(ticket.hold_time)
      .fromNow()} in ${location.name}.`;
  } else if (ticket.status === "rerequested") {
    status = `${capitalize(studentName)} re-requested ${possessive(
      staffName,
    )} help ${moment.utc(ticket.rerequest_time).fromNow()} in ${location.name}.`;
  } else {
    if (isStaff(state)) {
      status =
        capitalize(staffName) +
        " (Started helping " +
        ticketTimeSinceAssigned(ticket) +
        ") in " +
        location.name;
    } else {
      status = ticketStatus(state, ticket) + " in " + location.name;
    }
  }

  var description;
  if (isStaff(state) || ticketIsMine(state, ticket)) {
    description = ticket.description;
  }

  let question = ticketQuestion(app.state, ticket);

  return (
    <TicketLink state={state} ticket={ticket} independent={independent}>
      <div className="pull-left ticket-index">
        {ticketPosition(state, ticket)}
      </div>
      <h4 className="pull-left">
        {assignment.name} {question}
        <br className="visible-xs" />
        <small className="visible-xs ticket-status-xs">{status}</small>
        <small className="visible-xs ticket-desc-xs">{description}</small>
        <small className="visible-xs ticket-created-xs">
          Ticket created: {ticketTimeAgo(ticket)}
        </small>
      </h4>
      <h4 className="pull-left hidden-xs ticket-desc-md ">
        <small>{description}</small>
      </h4>
      <h4 className="pull-left hidden-xs ticket-created-md ">
        <small>Ticket created: {ticketTimeAgo(ticket)}</small>
      </h4>
      <h4 className="pull-right hidden-xs ticket-status-md">
        <small>
          {status}{" "}
          {moment
            .duration(moment.utc().diff(moment.utc(ticket.created)))
            .asDays() > 1 && <span className="badge"> Old Ticket </span>}
        </small>
      </h4>
    </TicketLink>
  );
};

export let TicketLink = ({ state, ticket, children, independent }) => {
  let highlight =
    ticketIsMine(state, ticket, true) || isTicketHelper(state, ticket);
  let link = ticketIsMine(state, ticket, true) || isStaff(state);
  let ticketClass = classNames({
    "ticket-row": true,
    clearfix: true,
    "ticket-link": link,
    "ticket-highlight": highlight,
    "ticket-independent": independent,
    "ticket-rerequested": ticket.status === "rerequested",
    "ticket-juggled": ticket.status === "juggled",
  });
  if (link) {
    return (
      <div className={ticketClass}>
        <Link to={`/tickets/${ticket.id}`} className="clearfix">
          {children}
        </Link>
      </div>
    );
  } else {
    return <div className={ticketClass}>{children}</div>;
  }
};
