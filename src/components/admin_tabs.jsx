import { Link } from "react-router-dom";
export function AdminTabs({ currentTab, partyAlias }) {
  const activeTab = currentTab === "admin" ? "general" : currentTab;

  const links = [
    "general",
    "tickets",
    "party",
    "assignments",
    "locations",
    "online",
  ];

  const body = links.map((link, index) => (
    <li
      key={link}
      role="presentation"
      className={activeTab === link ? "active" : ""}
    >
      <Link to={index ? "/admin/" + link : "/admin"}>
        {link === "party" ? partyAlias : link[0].toUpperCase() + link.slice(1)}
      </Link>
    </li>
  ));

  return <ul className="nav nav-tabs">{body}</ul>;
}
