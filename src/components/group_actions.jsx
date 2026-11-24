import { app } from "../app_instance";
import { isStaff, isTicketHelper } from "../state";

export let GroupActions = ({ state, status, tickets }) => {
  if (!isStaff(state)) return null;
  let ticket_ids = tickets.map((ticket) => ticket.id);
  const heldTickets = tickets.filter((ticket) =>
    ["juggled", "rerequested"].includes(ticket.status),
  );
  const myHeldTickets = heldTickets.filter((ticket) =>
    isTicketHelper(state, ticket),
  );
  const hasShuffledTickets = tickets.some(
    (ticket) => ticket.created !== ticket.sort_key,
  );
  var buttons;
  if (status === "pending") {
    buttons = [
      <button
        key="delete-all"
        onClick={() => {
          if (
            !confirm(
              `Are you sure you want to delete ${tickets.length} requests?`,
            )
          )
            return;
          app.makeRequest("delete", ticket_ids);
        }}
        className="btn btn-danger"
      >
        Delete all
      </button>,
      <button
        key="help-all"
        onClick={() => app.makeRequest("assign", ticket_ids, true)}
        className="btn btn-primary"
      >
        Help all
      </button>,
      !!myHeldTickets.length && (
        <button
          key="release-my-holds"
          onClick={() => {
            if (
              !confirm(
                `Are you sure you want to release all ${myHeldTickets.length} of your requests?`,
              )
            )
              return;
            app.makeRequest("release_holds", {
              ticket_ids: myHeldTickets.map((t) => t.id),
            });
          }}
          className="btn btn-warning"
        >
          Release my holds
        </button>
      ),
      hasShuffledTickets && (
        <button
          key="unshuffle"
          onClick={() => app.makeRequest("unshuffle_tickets", ticket_ids)}
          className="btn btn-info"
        >
          Unshuffle
        </button>
      ),
      state.config.enable_shuffle && (
        <button
          key="shuffle"
          onClick={() => app.makeRequest("shuffle_tickets", ticket_ids)}
          className="btn btn-warning"
        >
          Shuffle
        </button>
      ),
    ];
  } else if (status === "assigned") {
    buttons = [
      <button
        key="requeue-all"
        onClick={() => app.makeRequest("unassign", ticket_ids)}
        className="btn btn-warning"
      >
        Requeue all
      </button>,
      <button
        key="resolve-all"
        onClick={() => app.makeRequest("resolve", { ticket_ids: ticket_ids })}
        className="btn btn-primary"
      >
        Resolve all
      </button>,
    ];
  } else if (status === "held") {
    buttons = [
      <button
        key="release-all-holds"
        onClick={() => {
          if (
            !confirm(
              `Are you sure you want to release all ${heldTickets.length} of EVERYONE'S requests?`,
            )
          )
            return;
          app.makeRequest("release_holds", {
            ticket_ids: heldTickets.map((t) => t.id),
          });
        }}
        className="btn btn-danger"
      >
        Release all holds
      </button>,
      !!myHeldTickets.length && (
        <button
          key="release-my-holds"
          onClick={() => {
            if (
              !confirm(
                `Are you sure you want to release all ${myHeldTickets.length} of your requests?`,
              )
            )
              return;
            app.makeRequest("release_holds", {
              ticket_ids: myHeldTickets.map((t) => t.id),
            });
          }}
          className="btn btn-warning"
        >
          Release my holds
        </button>
      ),
    ];
  }

  // Right-aligned, with the count first and the first button last, as before.
  return (
    <div className="group-actions">
      <p>{tickets.length} selected</p>
      {buttons.filter(Boolean).reverse()}
    </div>
  );
};
