import { Link } from "react-router-dom";

// Links to the admin pages, shown as tabs.
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

  return (
    <nav className="nav nav-tabs mb-3" aria-label="Admin pages">
      {links.map((link, index) => {
        const active = activeTab === link;
        return (
          <Link
            key={link}
            className={active ? "nav-link active" : "nav-link"}
            aria-current={active ? "page" : undefined}
            to={index ? "/admin/" + link : "/admin"}
          >
            {link === "party"
              ? partyAlias
              : link[0].toUpperCase() + link.slice(1)}
          </Link>
        );
      })}
    </nav>
  );
}
