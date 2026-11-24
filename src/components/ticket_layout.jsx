import { useParams } from "react-router-dom";
import { Markdown } from "./markdown";
import React from "react";
import { app } from "../app_instance";
import { ChatBox } from "./chat_box";
import { DescriptionBox } from "./description_box";
import { Messages } from "./messages";
import { Navbar } from "./navbar";
import { NotFound } from "./not_found";
import { TicketButtons } from "./ticket_buttons";
import { UpdateAssignmentBox } from "./update_assignment_box";
import { UpdateLocationBox } from "./update_location_box";
import {
  getGroup,
  getTicket,
  isLoading,
  isStaff,
  isTicketHelper,
  ticketAssignment,
  ticketIsMine,
  ticketLocation,
  ticketQuestion,
  ticketStatus,
} from "../state";

export function TicketLayout({ loadTicket, state, socket }) {
  let id = +useParams().id;
  let ticket = getTicket(state, id);

  React.useEffect(() => {
    if (ticket == null) {
      loadTicket(id);
    }
  }, []);

  // The description being edited, reset whenever the ticket's saved one changes.
  const [description, setDescription] = React.useState("");
  const savedDescription = ticket ? ticket.description : undefined;
  const [shownDescription, setShownDescription] = React.useState(undefined);
  if (ticket && savedDescription !== shownDescription) {
    setShownDescription(savedDescription);
    setDescription(savedDescription);
  }

  const handleAssignmentSubmit = (args) => {
    app.makeRequest("update_ticket", Object.assign(args, { id }));
  };

  const handleDescriptionSubmit = () => {
    app.makeRequest("update_ticket", {
      id,
      description,
    });
  };

  if (ticket == null) {
    if (isLoading(state, id)) {
      return null; // TODO loading indicator instead of blank screen
    } else {
      return <NotFound />;
    }
  }

  if (!isStaff(state) && !ticketIsMine(state, ticket, true)) {
    return <NotFound />;
  }

  let assignment = ticketAssignment(state, ticket);
  let location = ticketLocation(state, ticket);
  let question = ticketQuestion(state, ticket);

  const group = getGroup(state, ticket.group_id);

  return (
    <div>
      <Navbar state={state} mode="queue" />
      <main>
        <div className="container">
          <Messages messages={state.messages} />
          {isStaff(state) &&
            ticket.status === "assigned" &&
            !isTicketHelper(state, ticket) && (
              <div className="alert alert-warning text-center">
                This ticket is being helped by{" "}
                <strong>{ticket.helper.name}</strong>.
              </div>
            )}
          <div className="row ticket">
            <div className="col-12">
              <h2 className="ticket-view-name text-center">
                {group
                  ? `${group.attendees[0].user.shortName}'s Group`
                  : ticket.status === "pending" && isStaff(state)
                    ? "Help to View Name"
                    : ticket.user.name}
                <small className="d-block text-body-secondary mt-1">
                  {assignment.name} {question} &middot; {location.name}
                  {location.link && ticket.call_url && ` (${ticket.call_url})`}
                </small>
              </h2>
              <p className="ticket-view-text text-center">
                {" "}
                {ticketStatus(state, ticket)}{" "}
              </p>
            </div>
          </div>
          <div className="row">
            <div className="col-12 col-md-6 offset-md-3">
              <hr />
              <DescriptionBox
                locked={!!ticket.group_id}
                state={state}
                ticket={ticket}
                prompt="Please describe your issue below:"
                placeholder={
                  state.config.default_description ||
                  "It would be helpful if you could describe your issue. For example," +
                    ' "I have a SyntaxError in my ___ function. I’ve tried using ____ and ____."'
                }
                description={description}
                onChange={setDescription}
                onSubmit={handleDescriptionSubmit}
              />
            </div>
          </div>
          {!ticket.group_id && (
            <div className="row">
              <div className="col-12 col-md-6 offset-md-3">
                <hr />
                <UpdateAssignmentBox
                  state={state}
                  elem={ticket}
                  onSubmit={handleAssignmentSubmit}
                />
              </div>
            </div>
          )}
          {!ticket.group_id && (
            <div className="row">
              <div className="col-12 col-md-6 offset-md-3">
                <hr />
                <UpdateLocationBox state={state} ticket={ticket} />
              </div>
            </div>
          )}
          <TicketButtons state={state} ticket={ticket} />
          <div className="row">
            <div className="col-12 col-md-6 offset-md-3">
              <hr />
              <ChatBox
                key={id}
                currentUser={state.currentUser}
                socket={socket}
                mode={group ? "group" : "ticket"}
                messages={group ? group.messages : ticket.messages}
                id={group ? group.id : id}
              />
            </div>
          </div>
          {state.config.ticket_prompt && (
            <div className="row">
              <div className="col-12 col-md-6 offset-md-3">
                <hr />
                <Markdown>{state.config.ticket_prompt}</Markdown>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
