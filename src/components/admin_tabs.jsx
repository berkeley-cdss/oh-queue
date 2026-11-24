import { Link } from "react-router-dom";
export function AdminTabs({ currentTab, partyAlias }) {
  if (currentTab === "admin") {
    currentTab = "general";
  }

  const links = [
    "general",
    "tickets",
    "party",
    "assignments",
    "locations",
    "online",
  ];

  const body = links.map((link, index) => (
    <li role="presentation" className={currentTab === link ? "active" : ""}>
      <Link to={index ? "/admin/" + link : "/admin"}>
        {link === "party" ? partyAlias : link[0].toUpperCase() + link.slice(1)}
      </Link>
    </li>
  ));

  return <ul className="nav nav-tabs">{body}</ul>;
}
