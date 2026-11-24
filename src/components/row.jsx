import { Link } from "react-router-dom";

// A row in a list of users or tickets: its title links to its page, and the link
// covers the whole row (Bootstrap's stretched-link).
export function Row({ title, link, prop1, prop2 }) {
  return (
    <div className="ticket-row ticket-link">
      <span className="ticket-index" />
      <div className="ticket-main">
        <div className="ticket-title">
          <Link to={link} className="stretched-link">
            {title}
          </Link>
        </div>
        <div className="ticket-details">{prop1}</div>
      </div>
      <div className="ticket-status">{prop2}</div>
    </div>
  );
}
