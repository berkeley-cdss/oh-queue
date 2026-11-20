let Queue = ({ state }) => {
  const { Redirect } = ReactRouterDOM;
  if (!state.currentUser && state.config.party_enabled) {
    return <Redirect to="/old" />;
  }
  let staff = isStaff(state);
  let myTicket = getMyTicket(state);
  let canAddTicket =
    !staff &&
    !myTicket &&
    (!state.config.party_enabled || state.config.allow_private_party_tickets);
  let showJumbotron = canAddTicket && !state.config.party_enabled;
  const myAssignedTickets = getTickets(state, "assigned").filter((ticket) =>
    isTicketHelper(state, ticket)
  );
  let pendingTickets = []
    .concat(
      ...getTickets(state, "rerequested").filter(
        (ticket) => isTicketHelper(state, ticket) || !ticket.helper
      )
    )
    .concat(...getTickets(state, "pending"))
    .concat(
      ...getTickets(state, "juggled").filter(
        (ticket) => isTicketHelper(state, ticket) || !ticket.helper
      )
    );
  let assignedTickets = getTickets(state, "assigned");
  let heldTickets = getTickets(state, "rerequested").concat(
    ...getTickets(state, "juggled")
  );
  if (!staff) {
    assignedTickets.push(...heldTickets);
  }
  let shouldHighlightAssigned = staff && getHelpingTicket(state);
  // Signed-out visitors get counts, not tickets: they see how long the queue is.
  let signedOut = !state.currentUser;
  let pendingCount = signedOut
    ? ticketCount(state, "pending")
    : pendingTickets.length;
  let assignedCount = signedOut
    ? ticketCount(state, "assigned")
    : assignedTickets.length;
  let signInToSee = (
    <div className="queue">
      <div className="no-results">
        <h4>
          <a href={loginPath()}>Sign in</a> to see the queue
        </h4>
      </div>
    </div>
  );
  let selectTab = (index) => {
    state.queueTabIndex = index;
    app.refresh();
  };
  let containerClass = classNames({
    container: true,
    "stub-jumbotron": !showJumbotron,
  });
  return (
    <div>
      {showJumbotron && <Jumbotron state={state} />}
      <div className={containerClass}>
        {!showJumbotron && canAddTicket && (
          <div className="col-xs-8 col-xs-offset-2">
            <div className="request-form">
              <RequestForm state={state} forceTicket />
            </div>
          </div>
        )}
        {!showJumbotron && <Messages messages={state.messages} />}
        <PresenceIndicator
          state={state}
          hideWaitTime={!state.config.show_presence}
        />
        <MyAssignedTickets state={state} tickets={myAssignedTickets} />
        {!!myAssignedTickets.length && <hr />}
        {staff && <FilterControls state={state} filter={state.filter} />}
        {staff && <hr />}
        <Tabs selectedIndex={state.queueTabIndex} onSelect={selectTab}>
          <Tab label={`Waiting (${pendingCount})`}>
            {signedOut ? (
              signInToSee
            ) : (
              <TicketList
                tickets={pendingTickets}
                status="pending"
                state={state}
              />
            )}
          </Tab>
          {staff && (
            <Tab label={`On Hold (${heldTickets.length})`}>
              <TicketList tickets={heldTickets} status="held" state={state} />
            </Tab>
          )}
          <Tab
            label={`Assigned (${assignedCount})`}
            shouldHighlight={shouldHighlightAssigned}
          >
            {signedOut ? (
              signInToSee
            ) : (
              <TicketList
                tickets={assignedTickets}
                status="assigned"
                state={state}
              />
            )}
          </Tab>
        </Tabs>
      </div>
    </div>
  );
};

let TicketList = ({ tickets, state, status }) => {
  let filteredTickets = applyFilter(state.filter, tickets);
  let items = filteredTickets.map((ticket) => (
    <Ticket key={ticket.id} state={state} ticket={ticket} />
  ));
  var body;
  if (tickets.length === 0) {
    body = (
      <div className="no-results">
        <h4>No help requests</h4>
      </div>
    );
  } else if (items.length === 0) {
    body = (
      <div className="no-results">
        <h4>No help requests matched your search</h4>
      </div>
    );
  } else {
    body = [
      <GroupActions
        key="group"
        tickets={filteredTickets}
        status={status}
        state={state}
      />,
    ].concat(items);
  }

  return <div className="queue">{body}</div>;
};
