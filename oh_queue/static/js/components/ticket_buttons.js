const LLM_HELP_TYPE_OPTIONS = [
  { value: "conceptual", label: "Conceptual" },
  { value: "debugging", label: "Debugging" },
  { value: "past_exams_studying", label: "Past Exams/ Studying" },
  { value: "other", label: "Other" },
];

const LLM_TIPS_INFLUENCE_OPTIONS = [
  { value: "helpful", label: "Helpful" },
  { value: "helpful_minimal", label: "Helpful, but minimal influence" },
  { value: "neutral", label: "Neutral" },
  { value: "not_helpful_but_accurate", label: "Not Helpful, but accurate" },
  { value: "not_helpful_at_all", label: "Not Helpful at all" },
];

function ResolveLlmFeedbackModal({
  isOpen,
  staffMode,
  studentHelpType,
  studentHelpOther,
  staffHelpType,
  staffHelpOther,
  llmTipsInfluence,
  errorMessage,
  onChangeStudentHelpType,
  onChangeStudentHelpOther,
  onChangeStaffHelpType,
  onChangeStaffHelpOther,
  onChangeLlmTipsInfluence,
  onClose,
  onSubmit,
}) {
  const root = React.useRef();

  React.useEffect(() => {
    if (isOpen) {
      $(root.current).modal("show");
    } else {
      $(root.current).modal("hide");
    }
  }, [isOpen]);

  React.useEffect(() => {
    $(root.current).on("hidden.bs.modal", onClose);
  }, []);

  return ReactDOM.createPortal(
    <div className="modal fade" ref={root} tabIndex="-1" role="dialog">
      <div className="modal-dialog" role="document">
        <div className="modal-content">
          <div className="modal-header">
            <button
              type="button"
              className="close"
              data-dismiss="modal"
              aria-label="Close"
            >
              <span aria-hidden="true">&times;</span>
            </button>
            <h4 className="modal-title">Before you resolve this ticket</h4>
          </div>
          <div className="modal-body">
            {errorMessage && (
              <div className="alert alert-danger">{errorMessage}</div>
            )}
            {!staffMode && (
              <div className="form-group">
                <label htmlFor="student-help-type">
                  What did course staff help with today?
                </label>
                <select
                  id="student-help-type"
                  className="form-control"
                  value={studentHelpType}
                  onChange={(e) => onChangeStudentHelpType(e.target.value)}
                >
                  <option value="">Select an option (optional)</option>
                  {LLM_HELP_TYPE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {!staffMode && studentHelpType === "other" && (
              <div className="form-group">
                <label htmlFor="student-help-other">Please describe</label>
                <input
                  id="student-help-other"
                  className="form-control"
                  type="text"
                  value={studentHelpOther}
                  onChange={(e) => onChangeStudentHelpOther(e.target.value)}
                />
              </div>
            )}
            {staffMode && (
              <React.Fragment>
                <div className="form-group">
                  <label htmlFor="staff-help-type">
                    What did you help the student with today?
                  </label>
                  <select
                    id="staff-help-type"
                    className="form-control"
                    value={staffHelpType}
                    onChange={(e) => onChangeStaffHelpType(e.target.value)}
                  >
                    <option value="">Select an option</option>
                    {LLM_HELP_TYPE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                {staffHelpType === "other" && (
                  <div className="form-group">
                    <label htmlFor="staff-help-other">Please describe</label>
                    <input
                      id="staff-help-other"
                      className="form-control"
                      type="text"
                      value={staffHelpOther}
                      onChange={(e) => onChangeStaffHelpOther(e.target.value)}
                    />
                  </div>
                )}
                <div className="form-group">
                  <label htmlFor="llm-tips-influence">
                    How did the LLM-tips influence your approach?
                  </label>
                  <select
                    id="llm-tips-influence"
                    className="form-control"
                    value={llmTipsInfluence}
                    onChange={(e) => onChangeLlmTipsInfluence(e.target.value)}
                  >
                    <option value="">Select an option</option>
                    {LLM_TIPS_INFLUENCE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              </React.Fragment>
            )}
          </div>
          <div className="modal-footer">
            <button
              type="button"
              className="btn btn-default"
              data-dismiss="modal"
            >
              Cancel
            </button>
            <button type="button" className="btn btn-primary" onClick={onSubmit}>
              Resolve
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}

class TicketButtons extends React.Component {
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
    this.submitResolveFeedback = this.submitResolveFeedback.bind(this);
    this.closeResolveFeedback = this.closeResolveFeedback.bind(this);

    this.refresher = null;
    this.state = {
      llmFeedbackModalOpen: false,
      pendingResolve: null,
      studentHelpType: "",
      studentHelpOther: "",
      staffHelpType: "",
      staffHelpOther: "",
      llmTipsInfluence: "",
      llmFeedbackError: "",
    };
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

  shouldPromptForLlmFeedback(staff) {
    let { state, ticket } = this.props;
    const llmEnabled =
      state.config.enable_llm_features === true ||
      state.config.enable_llm_features === "true";
    if (!llmEnabled || !ticket.use_llm || !ticket.llm_tips) {
      return false;
    }
    if (staff) {
      return true;
    }
    return !!ticket.helper;
  }

  requestResolve({ followRedirect = false, local = false } = {}) {
    let { state, ticket } = this.props;
    let staff = isStaff(state);
    if (this.shouldPromptForLlmFeedback(staff)) {
      this.setState({
        llmFeedbackModalOpen: true,
        pendingResolve: { followRedirect, local },
        llmFeedbackError: "",
      });
      return;
    }
    this.submitResolveRequest({ followRedirect, local });
  }

  submitResolveRequest({ followRedirect = false, local = false, payload = {} }) {
    const requestPayload = Object.assign(
      { ticket_ids: [this.props.ticket.id] },
      payload
    );
    if (local) {
      requestPayload.local = true;
    }
    app.makeRequest("resolve", requestPayload, followRedirect);
  }

  closeResolveFeedback() {
    if (this.state.llmFeedbackModalOpen) {
      this.setState({
        llmFeedbackModalOpen: false,
        pendingResolve: null,
        llmFeedbackError: "",
        studentHelpType: "",
        studentHelpOther: "",
        staffHelpType: "",
        staffHelpOther: "",
        llmTipsInfluence: "",
      });
    }
  }

  submitResolveFeedback() {
    let { state } = this.props;
    const staff = isStaff(state);
    const {
      studentHelpType,
      studentHelpOther,
      staffHelpType,
      staffHelpOther,
      llmTipsInfluence,
      pendingResolve,
    } = this.state;
    let errorMessage = "";
    if (staff) {
      if (!staffHelpType) {
        errorMessage = "Please select what you helped the student with.";
      } else if (staffHelpType === "other" && !staffHelpOther.trim()) {
        errorMessage = "Please describe what you helped the student with.";
      } else if (!llmTipsInfluence) {
        errorMessage = "Please select how the LLM-tips influenced your approach.";
      }
    } else if (studentHelpType === "other" && !studentHelpOther.trim()) {
      errorMessage = "Please describe what staff helped you with.";
    }

    if (errorMessage) {
      this.setState({ llmFeedbackError: errorMessage });
      return;
    }

    const payload = {};
    if (staff) {
      payload.staff_help_type = staffHelpType;
      if (staffHelpType === "other") {
        payload.staff_help_other = staffHelpOther.trim();
      }
      payload.llm_tips_influence = llmTipsInfluence;
    } else if (studentHelpType) {
      payload.student_help_type = studentHelpType;
      if (studentHelpType === "other") {
        payload.student_help_other = studentHelpOther.trim();
      }
    }

    this.setState({
      llmFeedbackModalOpen: false,
      pendingResolve: null,
      llmFeedbackError: "",
      studentHelpType: "",
      studentHelpOther: "",
      staffHelpType: "",
      staffHelpOther: "",
      llmTipsInfluence: "",
    });

    this.submitResolveRequest({
      followRedirect: pendingResolve && pendingResolve.followRedirect,
      local: pendingResolve && pendingResolve.local,
      payload,
    });
  }

  render() {
    let { embedded, state, ticket } = this.props;
    let staff = isStaff(state);

    function makeButton(text, style, action) {
      return (
        <button
          key={text}
          onClick={action}
          className={`btn btn-${style} btn-lg btn-block`}
        >
          {text}
        </button>
      );
    }

    function makeLink(text, style, href) {
      return (
        <a
          key={text}
          href={href}
          target="_blank"
          className={`btn btn-${style} btn-lg btn-block`}
        >
          {text}
        </a>
      );
    }

    let onlineButtons = [];
    let topButtons = [];
    let bottomButtons = [];

    if (staff && (ticket.status === "resolved" || ticket.status === "deleted")) {
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
              "_blank"
            )
          )
        );
      }
      if (!embedded && (ticket.doc_url || ticket.helper.doc_url)) {
        onlineButtons.push(
          makeButton("Open Shared Document", "info", () =>
            window.open(ticket.doc_url || ticket.helper.doc_url, "_blank")
          )
        );
      }

      bottomButtons.push(makeButton("Resolve", "default", this.resolve));
      if (staff) {
        if (isTicketHelper(state, ticket)) {
          topButtons.push(
            makeButton(
              "Resolve and Next in Room",
              "primary",
              this.resolveAndLocalNext
            )
          );
          topButtons.push(
            makeButton("Resolve and Next", "primary", this.resolveAndNext)
          );
          topButtons.push(
            makeButton("Come Back Later", "warning", this.comeBackLater)
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
    if (
      staff &&
      ticket.status === "assigned" &&
      state.config.show_okpy_backups
    ) {
      topButtons.push(
        makeLink(
          "View Backups",
          "default",
          "https://okpy.org/admin/course/" +
            state.config.okpy_endpoint_id +
            "/" +
            encodeURIComponent(ticket.user.email)
        )
      );
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
                this.returnTo
              )
            );
          } else {
            topButtons.push(
              makeButton("Continue helping", "warning", this.returnTo)
            );
          }
        } else {
          topButtons.push(makeButton("Take over", "warning", this.releaseToMe));
        }
        if (ticket.helper) {
          topButtons.push(
            makeButton("Release hold", "danger", this.releaseToAnyone)
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
              "warning disabled"
            )
          );
        } else {
          topButtons.push(
            makeButton("Re-request help", "warning", this.rerequest)
          );
        }
        bottomButtons.push(makeButton("Resolve", "default", this.resolve));
      }
    }
    if (ticket.status === "rerequested") {
      if (staff) {
        if (isTicketHelper(state, ticket)) {
          topButtons.push(
            makeButton("Continue helping", "warning", this.returnTo)
          );
        } else {
          topButtons.push(makeButton("Take over", "warning", this.releaseToMe));
        }
        if (ticket.helper) {
          topButtons.push(
            makeButton("Release hold", "danger", this.releaseToAnyone)
          );
        }
        bottomButtons.push(makeButton("Resolve", "default", this.resolve));
      } else {
        topButtons.push(
          makeButton("Help re-requested, wait for staff", "warning disabled")
        );
        bottomButtons.push(
          makeButton("Cancel request", "danger", this.cancelRerequest)
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
        {onlineButtons}
        {onlineHR}
        {topButtons}
        {hr}
        {bottomButtons}
      </React.Fragment>
    );

    const modal = (
      <ResolveLlmFeedbackModal
        isOpen={this.state.llmFeedbackModalOpen}
        staffMode={staff}
        studentHelpType={this.state.studentHelpType}
        studentHelpOther={this.state.studentHelpOther}
        staffHelpType={this.state.staffHelpType}
        staffHelpOther={this.state.staffHelpOther}
        llmTipsInfluence={this.state.llmTipsInfluence}
        errorMessage={this.state.llmFeedbackError}
        onChangeStudentHelpType={(value) =>
          this.setState({ studentHelpType: value })
        }
        onChangeStudentHelpOther={(value) =>
          this.setState({ studentHelpOther: value })
        }
        onChangeStaffHelpType={(value) =>
          this.setState({ staffHelpType: value })
        }
        onChangeStaffHelpOther={(value) =>
          this.setState({ staffHelpOther: value })
        }
        onChangeLlmTipsInfluence={(value) =>
          this.setState({ llmTipsInfluence: value })
        }
        onClose={this.closeResolveFeedback}
        onSubmit={this.submitResolveFeedback}
      />
    );

    if (embedded) {
      return (
        <React.Fragment>
          {contents}
          {modal}
        </React.Fragment>
      );
    }

    return (
      <div className="row">
        <div className="col-xs-12 col-md-6 col-md-offset-3">
          <div className="well">{contents}</div>
          {modal}
        </div>
      </div>
    );
  }
}
