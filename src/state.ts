import moment from "moment";
import { cancelNotification, notifyUser, playNewTicketSound } from "./common";

/* This file contains functions for manipulating the global state of the app.
 *
 * Its types are checked with `yarn typecheck`.
 */

export type User = {
  id: number;
  email: string;
  name: string;
  shortName: string;
  isStaff: boolean;
  call_url: string | null;
  doc_url: string | null;
};

export type Ticket = {
  id: number;
  status:
    "pending" | "assigned" | "resolved" | "deleted" | "juggled" | "rerequested";
  user: User;
  created: string; // ISO 8601 datetime string
  sort_key: string; // ISO 8601 datetime string
  rerequest_threshold: string | null; // ISO 8601 datetime string
  hold_time: string | null; // ISO 8601 datetime string
  rerequest_time: string | null; // ISO 8601 datetime string
  updated: string | null;
  location_id: number;
  assignment_id: number;
  question: string;
  description: string | null;
  helper: User | null;
  call_url: string;
  doc_url: string;
  group_id: number;
};

export type TicketAssignment = {
  id: number;
  name: string;
};

export type TicketLocation = {
  id: number;
  name: string;
};

export type Filter = {
  /* Selected options, as the form's values. null means do not filter by an attribute. */
  assignment_id: string | null;
  location_id: string | null;
  question: string | null;
};

export type Message = {
  id: number;
  category: string; // e.g. "danger", "warning"
  text: string;
  visible: boolean;
};

export type Group = {
  id: number;
  created: string; // ISO 8601 datetime string
  attendees: Array<GroupAttendance>;
  location_id: number;
  ticket_id: number | null;
  assignment_id: number;
  question: string | null;
  description: string | null;
  group_status: "active" | "resolved";
  call_url: string;
  doc_url: string;
};

export type GroupAttendance = {
  id: number;
  group_id: number;
  user: User;
  group_attendance_status: "present" | "gone";
};

export type State = {
  /* May be null if the user is not logged in. */
  currentUser: User | null;
  /* True on page load, before the initial websocket connection. */
  loaded: boolean;
  /* True if the websocket has disconnected. */
  offline: boolean;
  /* Ticket assignments */
  assignments: Record<number, TicketAssignment>;
  groups: Array<Group>;
  /* Ticket locations */
  locations: Record<number, TicketLocation>;
  /* Server configuration */
  /* Most values are strings; App parses the boolean ones. */
  config: Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  /* All known tickets, including ones that have been resolved or deleted.
   * We may have to load past tickets asynchronously though.
   * This is an ES6 Map from ticket ID to the ticket data.
   */
  tickets: Map<number, Ticket>;
  /* For signed-out visitors, who get no tickets: how many have each status. */
  ticketCounts: Record<string, number> | null;
  /* Ticket IDs for any tickets we are currently loading. */
  loadingTickets: Set<number>;
  /* Group IDs the server has no group for. */
  missingGroups: Set<number>;
  /* Current ticket filter. */
  filter: Filter;
  /* Selected queue tab. */
  queueTabIndex: number;
  /* Flashed messages. */
  messages: Array<Message>;
  nextMessageID: number;
};

export const initialState: State = {
  currentUser: null,
  loaded: false,
  offline: true,
  assignments: {},
  locations: {},
  config: {},
  groups: [],
  tickets: new Map(),
  ticketCounts: null,
  loadingTickets: new Set(),
  missingGroups: new Set(),
  filter: {
    location_id: null,
    assignment_id: null,
    question: null,
  },
  queueTabIndex: 0,
  messages: [],
  nextMessageID: 1,
};

export function ticketDisplayTime(ticket: Ticket): string {
  return moment.utc(ticket.created).local().format("h:mm A");
}

export function ticketTimeAgo(ticket: Ticket | Group): string {
  return moment.utc(ticket.created).fromNow();
}

export function ticketTimeSinceAssigned(ticket: Ticket): string {
  return moment.utc(ticket.updated).fromNow();
}

export function ticketTimeToReRequest(ticket: Ticket): string {
  return moment.utc(ticket.rerequest_threshold).fromNow();
}

export function isPending(ticket: Ticket): boolean {
  return ticket.status === "pending";
}

export function isActive(ticket: Ticket): boolean {
  return ["pending", "assigned", "juggled", "rerequested"].includes(
    ticket.status,
  );
}

export function ticketAssignment(
  state: State,
  ticket: Ticket,
): TicketAssignment {
  return state.assignments[ticket.assignment_id];
}

export function ticketLocation(state: State, ticket: Ticket): TicketLocation {
  return state.locations[ticket.location_id];
}

export function ticketQuestion(state: State, ticket: Ticket | Group): string {
  // A question number, such as "3", is shown as "Q3"; anything else as it is.
  const question = (ticket.question ?? "").trim();
  if (/^\d+$/.test(question)) {
    return "Q" + parseInt(question, 10);
  }
  return question;
}

export function ticketStatus(state: State, ticket: Ticket): string {
  if (ticket.status === "assigned" && ticket.helper) {
    return (
      "Being helped by " +
      (isTicketHelper(state, ticket) ? "you" : ticket.helper.name)
    );
  } else if (ticket.status === "resolved") {
    if (ticket.helper) {
      return "Resolved by " + ticket.helper.name;
    } else {
      return "Resolved";
    }
  } else if (ticket.status === "deleted") {
    return "Deleted";
  } else if (ticket.status === "juggled") {
    return ticket.group_id ? "Working in a group" : "Working solo";
  } else if (ticket.status === "rerequested") {
    return `Waiting for ${
      isTicketHelper(state, ticket)
        ? "you"
        : ticket.helper
          ? ticket.helper.name
          : "any assistant"
    } to come back`;
  } else {
    return "Queued";
  }
}

export function ticketPosition(
  state: State,
  ticket: Ticket,
): string | undefined {
  const index = getTickets(state, "pending").findIndex(
    (pendingTicket) => pendingTicket.id === ticket.id,
  );
  if (index != -1) {
    return "#" + (index + 1);
  }
}

export function isStaff(state: State): boolean {
  return state.currentUser != null && state.currentUser.isStaff;
}

export function getTicket(state: State, id: number): Ticket | undefined {
  return state.tickets.get(id);
}

export function setTicket(state: State, ticket: Ticket): void {
  if (ticketIsMine(state, ticket, true)) {
    const oldTicket = getMyTicket(state);
    if (oldTicket) {
      if (oldTicket.status === "pending" && ticket.status === "assigned") {
        const location = ticketLocation(state, ticket);
        notifyUser(
          "Your name is being called",
          (ticket.helper?.name ?? "Staff") +
            " is looking for you in " +
            location.name,
          ticket.id + ".assign",
        );
      } else if (
        oldTicket.status === "assigned" &&
        ticket.status !== "assigned"
      ) {
        cancelNotification(ticket.id + ".assign");
      }
    }
  }
  /* New ticket notifications for staff */
  if (isStaff(state) && state.config.send_ticket_notifications) {
    const oldTicket = getTicket(state, ticket.id);
    if (!oldTicket && ticket.status === "pending") {
      const assignment = ticketAssignment(state, ticket);
      const location = ticketLocation(state, ticket);
      const question = ticketQuestion(state, ticket);
      notifyUser(
        "New request for " + assignment.name + " " + question,
        location.name,
        ticket.id + ".create",
      );
      playNewTicketSound();
    } else if (ticket.status !== "pending") {
      cancelNotification(ticket.id + ".create");
    }
  }
  state.tickets.set(ticket.id, ticket);
}

export function loadTicket(state: State, id: number): void {
  state.loadingTickets.add(id);
}

export function isLoading(state: State, id: number): boolean {
  return state.loadingTickets.has(id);
}

export function receiveTicket(state: State, id: number, ticket: Ticket | null) {
  if (ticket != null) {
    setTicket(state, ticket);
  }
  state.loadingTickets.delete(id);
}

/* Return an array of pending tickets, sorted by queue time.
 */
export function getTickets(state: State, status: string): Array<Ticket> {
  return Array.from(state.tickets.values())
    .filter((ticket) => ticket.status === status)
    .sort((a, b) => {
      if (a.sort_key < b.sort_key) {
        return -1;
      } else if (a.sort_key > b.sort_key) {
        return 1;
      } else {
        return 0;
      }
    });
}

/* How many active tickets have this status: from the counts the server
 * sends signed-out visitors, or else from the tickets.
 */
export function ticketCount(state: State, status: string): number {
  if (state.ticketCounts) {
    return state.ticketCounts[status] || 0;
  }
  return getTickets(state, status).length;
}

export function applyFilter(
  filter: Filter,
  tickets: Array<Ticket>,
): Array<Ticket> {
  const assignmentId = parseInt(filter.assignment_id ?? "");
  if (!isNaN(assignmentId)) {
    tickets = tickets.filter((ticket) => ticket.assignment_id === assignmentId);
  }
  const locationId = parseInt(filter.location_id ?? "");
  if (!isNaN(locationId)) {
    tickets = tickets.filter((ticket) => ticket.location_id === locationId);
  }
  if (filter.question) {
    tickets = tickets.filter((ticket) => ticket.question === filter.question);
  }
  return tickets;
}

export function ticketIsMine(
  state: State,
  ticket: Ticket,
  includeGroup?: boolean,
): boolean {
  const myGroup = includeGroup ? getMyGroup(state) : undefined;
  return (
    state.currentUser != null &&
    ((ticket.user && state.currentUser.id === ticket.user.id) ||
      (myGroup != null && myGroup.id === ticket.group_id))
  );
}

export function isTicketHelper(state: State, ticket: Ticket): boolean {
  return (
    state.currentUser != null &&
    ticket.helper != null &&
    state.currentUser.id === ticket.helper.id
  );
}

/* Return the current user's active ticket. */
export function getMyTicket(state: State): Ticket | undefined {
  return Array.from(state.tickets.values()).find(
    (ticket) => isActive(ticket) && ticketIsMine(state, ticket),
  );
}

/* Return the first ticket the current user is helping. */
export function getHelpingTicket(state: State): Ticket | undefined {
  return Array.from(state.tickets.values()).find(
    (ticket) => isActive(ticket) && isTicketHelper(state, ticket),
  );
}

export function addMessage(
  state: State,
  text: string,
  category: string,
): number {
  const id = state.nextMessageID;
  state.messages.push({
    id,
    text,
    category,
    visible: true,
  });
  state.nextMessageID += 1;
  return id;
}

export function clearMessage(state: State, id: number): void {
  const message = state.messages.find((message) => message.id === id);
  if (message) {
    message.visible = false;
  }
}

export const timeComparator = (a: moment.Moment, b: moment.Moment) =>
  a.isAfter(b) ? 1 : -1;

export function getGroup(state: State, group_id: number): Group | undefined {
  return state.groups.find(({ id }) => id === group_id);
}

export function setGroup(state: State, group: Group): void {
  if (!group.id) {
    return;
  }
  const oldGroup = getGroup(state, group.id);
  if (oldGroup) {
    state.groups.splice(state.groups.indexOf(oldGroup), 1);
  }
  state.groups.push(group);
  state.groups.sort((a, b) => a.id - b.id);
}

/* The server's answer to loading a group by ID: the group, or else nothing or
 * an error (for an ID that isn't one), so there's no such group. */
export function receiveGroup(state: State, id: number, group: Group | null) {
  if (group != null && group.id === id) {
    setGroup(state, group);
  } else {
    state.missingGroups.add(id);
  }
}

export function isGroupMissing(state: State, id: number): boolean {
  return state.missingGroups.has(id);
}

export function groupIsActive(group: Group): boolean {
  return group.group_status === "active";
}

export function groupIsMine(state: State, group: Group): boolean {
  const { currentUser } = state;
  return (
    currentUser != null &&
    group.attendees.some((attendance) => attendance.user.id === currentUser.id)
  );
}

export function getMyGroup(state: State): Group | undefined {
  return Array.from(state.groups.values()).find(
    (group) => groupIsActive(group) && groupIsMine(state, group),
  );
}
