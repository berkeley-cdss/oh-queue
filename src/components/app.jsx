import React from "react";
import {
  BrowserRouter,
  Route,
  Routes,
  useNavigate,
  useParams,
} from "react-router-dom";
import { setApp } from "../app_instance";
import { isPartyRoot } from "../common";
import { ActivityLogLayout } from "./activity_log_layout";
import { AdminLayout } from "./admin_layout";
import { ErrorView } from "./error_view";
import { Home } from "./home";
import { Party } from "./party";
import { PartyGroupLayout } from "./party_group_layout";
import { PresenceIndicator } from "./presence_indicator";
import { StaffOnlineSetup } from "./staff_online_setup";
import { TicketLayout } from "./ticket_layout";
import { UserLayout } from "./user_layout";
import { Socket } from "../socket";
import {
  addMessage,
  clearMessage,
  initialState,
  isStaff,
  loadTicket,
  receiveGroup,
  receiveTicket,
  setGroup,
  setTicket,
} from "../state";

/* This component holds the global application state, and manages the websocket
 * connection. To update the state, call a method on the "app" object
 * (app_instance.js), e.g. as
 *
 *     app.addMessage("Something bad happened", "danger");
 *
 * Because it sits at the root of React heirarchy, any state changes in the app
 * will cause the entire app to re-render, so any state changes are reflected
 * instantly.
 *
 * All other React components are "stateless". Many of them are simply pure
 * functions that take the state and produce HTML. A few are slightly more
 * complicated in that they have to interact with jQuery or the network.
 *
 * NB: calling app methods inside a render() method will result in an infinite
 * loop.
 */
export class App extends React.Component {
  constructor(props) {
    super(props);
    setApp(this);
    this.state = initialState;
    this.socket = new Socket();

    this.socket.on("connect", () => {
      this.setOffline(false);
    });
    this.socket.on("disconnect", () => this.setOffline(true));
    this.socket.on("state", (data, callback) => {
      this.updateState(data);
      if (callback) {
        callback();
      }
    });
    this.socket.on("event", (data) => this.updateTicket(data));
    this.socket.on("group_event", (data) => this.updateGroup(data));

    this.loadTicket = this.loadTicket.bind(this);
    this.loadGroup = this.loadGroup.bind(this);
    this.setNavigate = (navigate) => {
      this.navigate = navigate;
    };
  }

  refresh() {
    this.setState(this.state);
  }

  setOffline(offline) {
    this.state.offline = offline;
    this.refresh();
  }

  updateState(data) {
    if (Array.isArray(data.assignments)) {
      this.state.assignments = {};
      for (var assignment of data.assignments) {
        this.state.assignments[assignment.id] = assignment;
      }
    }
    if (Array.isArray(data.locations)) {
      this.state.locations = {};
      for (var location of data.locations) {
        this.state.locations[location.id] = location;
      }
    }
    if (Array.isArray(data.tickets)) {
      this.state.ticketCounts = data.ticket_counts || null;
      const ticketIDs = new Set();
      for (var ticket of data.tickets) {
        setTicket(this.state, ticket);
        ticketIDs.add(ticket.id);
      }
      const oldTicketIDs = this.state.tickets.keys();
      for (const oldTicketID of oldTicketIDs) {
        if (!ticketIDs.has(oldTicketID)) {
          this.state.tickets.delete(oldTicketID);
        }
      }
    }
    if (Object.hasOwn(data, "config")) {
      this.state.config = data.config;
      for (const key of [
        "party_enabled",
        "allow_private_party_tickets",
        "show_presence",
        "enable_shuffle",
        "send_ticket_notifications",
      ]) {
        this.state.config[key] = JSON.parse(this.state.config[key]);
      }
    }
    if (Object.hasOwn(data, "current_user")) {
      this.state.currentUser = data.current_user;
    }
    if (Object.hasOwn(data, "groups")) {
      this.state.groups = Array.from(data.groups).sort((a, b) => a.id - b.id);
    }
    if (Object.hasOwn(data, "presence")) {
      this.state.presence = data.presence;
    }
    this.state.loaded = true;
    this.refresh();
  }

  shouldNotify(ticket, type) {
    return isStaff(this.state) && type === "create";
  }

  updateTicket(data) {
    setTicket(this.state, data.ticket);
    this.refresh();
  }

  updateGroup(data) {
    setGroup(this.state, data.group);
    this.refresh();
  }

  loadTicket(id) {
    loadTicket(this.state, id);
    this.refresh();
    this.socket.emit("load_ticket", id, (ticket) => {
      receiveTicket(this.state, id, ticket);
      this.refresh();
    });
  }

  loadGroup(id) {
    if (isStaff(this.state)) {
      this.socket.emit("load_group", id, (group) => {
        receiveGroup(this.state, id, group);
        this.refresh();
      });
    }
  }

  selectQueueTab(index) {
    this.state.queueTabIndex = index;
    this.refresh();
  }

  toggleFilter() {
    this.state.filter.enabled = !this.state.filter.enabled;
    this.refresh();
  }

  setFilter(filter) {
    filter.enabled = !!this.state.filter.enabled;
    this.state.filter = filter;
    this.refresh();
  }

  addMessage(message, category, ttl) {
    const id = addMessage(this.state, message, category);
    this.refresh();
    if (ttl) {
      setTimeout(() => this.clearMessage(id), ttl);
    }
  }

  clearMessage(id) {
    clearMessage(this.state, id);
    this.refresh();
  }

  makeRequest(eventType, request, follow_redirect = false, callback) {
    if (typeof request === "function") {
      follow_redirect = request;
      request = undefined;
    }
    if (typeof follow_redirect === "function") {
      callback = follow_redirect;
      follow_redirect = false;
    }
    let cb = (response) => {
      if (response == null) {
        if (callback) callback(response);
        return;
      }
      let messages = response.messages || [];
      for (var message of messages) {
        this.addMessage(message.text, message.category, message.ttl);
      }
      if (follow_redirect && response.redirect) {
        this.navigate(response.redirect);
      }
      if (callback) callback(response);
    };
    // A promise of whether the request succeeded (see Socket.emit).
    if (request !== undefined) {
      return this.socket.emit(eventType, request, cb);
    } else {
      return this.socket.emit(eventType, cb);
    }
  }

  render() {
    let state = this.state;

    const Root = isPartyRoot(state) ? Party : Home;

    return (
      <BrowserRouter basename={window.basePath}>
        <RememberNavigate onNavigate={this.setNavigate} />
        <div>
          <Routes>
            <Route path="/" element={<Root state={state} />} />
            <Route path="/party" element={<Party state={state} />} />
            <Route path="/queue" element={<Home state={state} />} />
            <Route
              path="/online_setup"
              element={<StaffOnlineSetup state={state} />}
            />
            <Route path="/admin/*" element={<AdminLayout state={state} />} />
            <Route
              path="/activity_log/*"
              element={<ActivityLogLayout state={state} />}
            />
            <Route path="/error/*" element={<ErrorView state={state} />} />
            <Route
              path="/presence/*"
              element={<PresenceIndicator state={state} />}
            />
            <Route
              path="/tickets/:id/*"
              element={
                <ByID
                  page={TicketLayout}
                  state={state}
                  socket={this.socket}
                  loadTicket={this.loadTicket}
                />
              }
            />
            <Route
              path="/groups/:id/*"
              element={
                <ByID
                  page={PartyGroupLayout}
                  state={state}
                  socket={this.socket}
                  loadGroup={this.loadGroup}
                />
              }
            />
            <Route path="/user/:id/*" element={<UserLayout state={state} />} />
            <Route
              path="*"
              element={<ErrorView state={state} message="Page Not Found" />}
            />
          </Routes>
        </div>
      </BrowserRouter>
    );
  }
}

// A new page for each ticket or group, so nothing typed into or loaded for one
// (a description, an assignment) carries over to the next, as after Next Ticket.
function ByID({ page: Page, ...props }) {
  const { id } = useParams();
  return <Page key={id} {...props} />;
}

// Gives App the router's navigate function, for following the server's redirects.
function RememberNavigate({ onNavigate }) {
  const navigate = useNavigate();
  React.useEffect(() => {
    onNavigate(navigate);
  }, [navigate, onNavigate]);
  return null;
}
