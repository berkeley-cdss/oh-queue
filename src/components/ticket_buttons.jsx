import moment from "moment";
import React from "react";
import { app } from "../app_instance";
import {
  isStaff,
  isTicketHelper,
  ticketLocation,
  ticketTimeToReRequest,
} from "../state";

export class TicketButtons extends React.Component {
  constructor(props) {
    super(props);
    this.assign = this.assign.bind(this);
    this.returnTo = this.returnTo.bind(this);
    this.delete = this.delete.bind(this);
    this.resolveAndNext = this.resolveAndNext.bind(this);
    this.resolveAndLocalNext = this.resolveAndLocalNext.bind(this);
    this.comeBackLater = this.comeBackLater.bind(this);
    this.releaseToAnyone = this.releaseToAnyone.bind(this);
    this.releaseToMe = this.releaseToMe.bind(this);
    this.rerequest = this.rerequest.bind(this);
    this.cancelRerequest = this.cancelRerequest.bind(this);
    this.resolve = this.resolve.bind(this);
    this.unassign = this.unassign.bind(this);
    this.reassign = this.reassign.bind(this);
    this.next = this.next.bind(this);
    this.requestResolve = this.requestResolve.bind(this);

    this.refresher = null;
  }

  componentDidMount() {
    this.refresher = setInterval(this.forceUpdate.bind(this), 1000);
  }

  componentWillUnmount() {
    clearInterval(this.refresher);
  }

  assign() {
    app.makeRequest("assign", [this.props.ticket.id], true);
  }

  returnTo() {
    app.makeRequest("return_to", [this.props.ticket.id]);
  }

  delete() {
    if (!confirm("Delete this ticket?")) return;
    app.makeRequest("delete", [this.props.ticket.id]);
  }

  resolveAndNext() {
    this.requestResolve({ followRedirect: true });
  }

  resolveAndLocalNext() {
    this.requestResolve({ followRedirect: true, local: true });
  }

  comeBackLater() {
    app.makeRequest("juggle", { ticket_ids: [this.props.ticket.id] }, true);
  }

  releaseToAnyone() {
    if (!confirm("Release this ticket to anyone else?")) return;
    app.makeRequest("release_holds", { ticket_ids: [this.props.ticket.id] });
  }

  releaseToMe() {
    if (
      this.props.ticket.helper &&
      !confirm("Take over responsibility for this ticket?")
    )
      return;
    app.makeRequest("release_holds", {
      ticket_ids: [this.props.ticket.id],
      to_me: true,
    });
  }

  rerequest() {
    app.makeRequest("rerequest", { ticket_ids: [this.props.ticket.id] });
  }

  cancelRerequest() {
    app.makeRequest("cancel_rerequest", { ticket_ids: [this.props.ticket.id] });
  }

  resolve() {
    this.requestResolve();
  }

  unassign() {
    app.makeRequest("unassign", [this.props.ticket.id]);
  }

  reassign() {
    if (!confirm("Reassign this ticket?")) return;
    app.makeRequest("assign", [this.props.ticket.id], true);
  }

  next() {
    app.makeRequest("next", [this.props.ticket.id], true);
  }

  requestResolve({ followRedirect = false, local = false } = {}) {
    const payload = { ticket_ids: [this.props.ticket.id] };
    if (local) {
      payload.local = true;
    }
    app.makeRequest("resolve", payload, followRedirect);
  }

  render() {
    let { embedded, state, ticket } = this.props;
    let staff = isStaff(state);

    function makeButton(text, style, action) {
      return (
        <button
          type="button"
          key={text}
          onClick={action}
          // "default" was Bootstrap 3's plain button; Bootstrap 5's is the outline one.
          className={`btn btn-${style === "default" ? "outline-secondary" : style} btn-lg w-100`}
        >
          {text}
        </button>
      );
    }

    let onlineButtons = [];
    let topButtons = [];
    let bottomButtons = [];

    if (
      staff &&
      (ticket.status === "resolved" || ticket.status === "deleted")
    ) {
      topButtons.push(makeButton("Revive", "danger", this.unassign));
    }

    if (ticket.status === "pending") {
      bottomButtons.push(makeButton("Delete", "danger", this.delete));
      if (staff) {
        topButtons.push(makeButton("Help", "primary", this.assign));
      }
    }
    if (ticket.status === "assigned") {
      if (
        !embedded &&
        (ticketLocation(state, ticket).link ||
          ticket.call_url ||
          ticket.helper.call_url)
      ) {
        onlineButtons.push(
          makeButton("Join Call", "success", () =>
            window.open(
              ticketLocation(state, ticket).link ||
                ticket.call_url ||
                ticket.helper.call_url,
              "_blank",
            ),
          ),
        );
      }
      if (!embedded && (ticket.doc_url || ticket.helper.doc_url)) {
        onlineButtons.push(
          makeButton("Open Shared Document", "info", () =>
            window.open(ticket.doc_url || ticket.helper.doc_url, "_blank"),
          ),
        );
      }

      bottomButtons.push(makeButton("Resolve", "default", this.resolve));
      if (staff) {
        if (isTicketHelper(state, ticket)) {
          topButtons.push(
            makeButton(
              "Resolve and Next in Room",
              "primary",
              this.resolveAndLocalNext,
            ),
          );
          topButtons.push(
            makeButton("Resolve and Next", "primary", this.resolveAndNext),
          );
          topButtons.push(
            makeButton("Come Back Later", "warning", this.comeBackLater),
          );
          bottomButtons.push(makeButton("Requeue", "default", this.unassign));
        } else {
          topButtons.push(makeButton("Reassign", "warning", this.reassign));
          topButtons.push(makeButton("Next Ticket", "default", this.next));
        }
      }
    }
    if (
      staff &&
      (ticket.status === "resolved" || ticket.status === "deleted")
    ) {
      topButtons.push(makeButton("Next Ticket", "default", this.next));
    }
    if (ticket.status === "juggled") {
      const isWaiting = moment.utc(ticket.rerequest_threshold).isAfter();
      if (staff) {
        if (isTicketHelper(state, ticket)) {
          if (isWaiting) {
            topButtons.push(
              makeButton(
                "Continue helping (ahead of schedule)",
                "danger",
                this.returnTo,
              ),
            );
          } else {
            topButtons.push(
              makeButton("Continue helping", "warning", this.returnTo),
            );
          }
        } else {
          topButtons.push(makeButton("Take over", "warning", this.releaseToMe));
        }
        if (ticket.helper) {
          topButtons.push(
            makeButton("Release hold", "danger", this.releaseToAnyone),
          );
        }
        bottomButtons.push(makeButton("Delete", "danger", this.delete));
        bottomButtons.push(makeButton("Resolve", "default", this.resolve));
      } else {
        if (isWaiting) {
          const remainingTime = ticketTimeToReRequest(ticket);
          topButtons.push(
            makeButton(
              "You can re-request help " + remainingTime,
              "warning disabled",
            ),
          );
        } else {
          topButtons.push(
            makeButton("Re-request help", "warning", this.rerequest),
          );
        }
        bottomButtons.push(makeButton("Resolve", "default", this.resolve));
      }
    }
    if (ticket.status === "rerequested") {
      if (staff) {
        if (isTicketHelper(state, ticket)) {
          topButtons.push(
            makeButton("Continue helping", "warning", this.returnTo),
          );
        } else {
          topButtons.push(makeButton("Take over", "warning", this.releaseToMe));
        }
        if (ticket.helper) {
          topButtons.push(
            makeButton("Release hold", "danger", this.releaseToAnyone),
          );
        }
        bottomButtons.push(makeButton("Resolve", "default", this.resolve));
      } else {
        topButtons.push(
          makeButton("Help re-requested, wait for staff", "warning disabled"),
        );
        bottomButtons.push(
          makeButton("Cancel request", "danger", this.cancelRerequest),
        );
      }
    }

    let onlineHR = onlineButtons.length ? <hr /> : null;
    let hr = topButtons.length && bottomButtons.length ? <hr /> : null;

    if (!(topButtons.length || bottomButtons.length)) {
      return null;
    }

    const contents = (
      <React.Fragment>
        {!!onlineButtons.length && (
          <div className="d-grid gap-2">{onlineButtons}</div>
        )}
        {onlineHR}
        {!!topButtons.length && (
          <div className="d-grid gap-2">{topButtons}</div>
        )}
        {hr}
        {!!bottomButtons.length && (
          <div className="d-grid gap-2">{bottomButtons}</div>
        )}
      </React.Fragment>
    );

    if (embedded) {
      return contents;
    }

    return (
      <div className="row">
        <div className="col-12 col-md-6 offset-md-3">
          <div className="card card-body bg-body-tertiary">{contents}</div>
        </div>
      </div>
    );
  }
}
