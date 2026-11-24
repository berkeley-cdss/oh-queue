import { Ticket } from "./ticket";

export function MyAssignedTickets({ state, tickets }) {
  return (
    !!tickets.length && (
      <section className="mb-3">
        <h2 className="assigned-tickets-header">Your Assigned Tickets</h2>
        {tickets.map((ticket) => (
          <Ticket key={ticket.id} state={state} ticket={ticket} independent />
        ))}
      </section>
    )
  );
}
