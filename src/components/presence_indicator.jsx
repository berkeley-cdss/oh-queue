import { Link } from "react-router-dom";
import { Markdown } from "./markdown";
import React from "react";
import Alert from "react-bootstrap/Alert";
import Collapse from "react-bootstrap/Collapse";
import { app } from "../app_instance";
import { MagicWordDisplay } from "./magic_word_display";
import { isStaff, ticketCount } from "../state";

export let PresenceIndicator = ({ state, hideWaitTime, hideWelcome }) => {
  let presence = state.presence;
  let numStudentsOnline = presence && presence.students ? presence.students : 0;
  let numStaffOnline = presence && presence.staff ? presence.staff : 0;
  let color = numStaffOnline ? "success" : "warning";
  let pendingCount = ticketCount(state, "pending");
  let assignedCount = ticketCount(state, "assigned");

  var studentMessage = numStudentsOnline + " students";
  var staffMessage = numStaffOnline + " assistants";

  if (numStudentsOnline === 1) {
    studentMessage = studentMessage.slice(0, -1);
  }
  if (numStaffOnline === 1) {
    staffMessage = staffMessage.slice(0, -1);
  }

  let message = studentMessage + " and " + staffMessage + " currently online.";

  // PARAM 1: expected service time ~ Exponential(1/10)
  var avgHelpTime = 10;

  // how many assistants are unoccupied
  var availableAssistants = numStaffOnline - assignedCount;

  // how many students need help, assuming all avaiable assistants are assigned
  var stillNeedHelp = Math.max(0, pendingCount - availableAssistants);

  // a class for the time's color, dark enough to read on the alert (style.css)
  var waitColor = "wait-unknown";

  // catch if there actually are no assistants available
  if (numStaffOnline == 0) {
    var timeRange = "??";
  } else {
    // min of numStaffOnline exponentials is exponential, take expectation
    var expectedWaitFirst = Math.ceil(avgHelpTime / numStaffOnline);
    // standard deviation of exponential equals the expectation
    var stdDev = expectedWaitFirst;

    // expectation for stillNeedHelp + 1th student on queue
    var expectedWaitTotal = (stillNeedHelp + 1) * expectedWaitFirst;

    // PARAM 2: (75% conf interval by CLT, 1.15 is from zscore of Normal)
    var bound = (1.15 * stdDev) / Math.sqrt(numStaffOnline);

    // interval bounds
    var estWaitTimeMin = Math.max(0, Math.floor(expectedWaitTotal - bound));
    var estWaitTimeMax = Math.ceil(expectedWaitTotal + bound);

    // colors for the time
    if (expectedWaitTotal <= 5) {
      waitColor = "wait-short";
    } else if (expectedWaitTotal < 10) {
      waitColor = "wait-medium";
    } else if (expectedWaitTotal < 25) {
      waitColor = "wait-long";
    } else {
      waitColor = "wait-very-long";
    }

    // concatenate time range string
    timeRange = estWaitTimeMin + " - " + estWaitTimeMax;
    if (estWaitTimeMax > 120) {
      timeRange = "> 120";
    }
  }

  var welcomeMessage = state.config.welcome;

  const openQueue = () => {
    app.makeRequest(`update_config`, {
      key: "is_queue_open",
      value: "true",
    });
  };

  return (
    <div className="presence">
      {state.config.is_queue_open === "false" &&
        (state.config.party_enabled || isStaff(state)) && (
          <DismissibleAlert variant="danger">
            <h2 className="alert-heading h4">The queue is currently closed!</h2>
            {state.currentUser && state.currentUser.isStaff && (
              <button className="btn btn-primary" onClick={openQueue}>
                Open queue
              </button>
            )}
          </DismissibleAlert>
        )}

      {!hideWelcome && (
        <DismissibleAlert variant="info">
          <Markdown>{welcomeMessage}</Markdown>
        </DismissibleAlert>
      )}

      {state.config.online_active === "true" &&
        state.currentUser &&
        state.currentUser.isStaff &&
        [
          state.config.students_set_online_link,
          state.config.students_set_online_doc,
        ].includes("false") && (
          <DismissibleAlert variant="warning">
            <h2 className="alert-heading h5">
              Configure Online Queue Settings
            </h2>
            <p className="mb-0">
              Remember to go to <Link to="/online_setup">Online Setup</Link> to
              configure your settings for video calls and shared documents,
              otherwise you will not be able to interact with students on the
              Online Queue.
            </p>
          </DismissibleAlert>
        )}

      {!hideWaitTime && (
        <DismissibleAlert variant={color}>
          <h2 className="alert-heading h5">
            Estimated wait time:{" "}
            <strong className={waitColor}>{timeRange}</strong> minutes
          </h2>
          <p className="mb-2">{message}</p>
          <MagicWordDisplay state={state} />
          {presence && state.currentUser && state.currentUser.isStaff && (
            <OnlineAssistants staff={presence.staff_list} />
          )}
        </DismissibleAlert>
      )}
    </div>
  );
};

// An alert with a button to close it, for the rest of the visit to this page.
function DismissibleAlert({ variant, children }) {
  const [shown, setShown] = React.useState(true);
  return (
    <Alert
      variant={variant}
      dismissible
      closeLabel="Dismiss"
      show={shown}
      onClose={() => setShown(false)}
    >
      {children}
    </Alert>
  );
}

// For staff: a button that shows who's helping, with their email addresses.
function OnlineAssistants({ staff }) {
  const [open, setOpen] = React.useState(false);
  const id = React.useId();
  return (
    <>
      <button
        type="button"
        className="btn btn-link p-0"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(!open)}
      >
        See online assistants.
      </button>
      <Collapse in={open}>
        <div id={id}>
          <ul className="mt-2 mb-0">
            {staff.map(([email, name]) => (
              <li key={email}>
                {name} (<a href={`mailto:${email}`}>{email}</a>)
              </li>
            ))}
          </ul>
        </div>
      </Collapse>
    </>
  );
}
