import { Route, Routes, useLocation } from "react-router-dom";
import { AdminAssignmentsManager } from "./admin_assignments_manager";
import { AdminConfigManager } from "./admin_config_manager";
import { AdminLocationsManager } from "./admin_locations_manager";
import { AdminOnlineManager } from "./admin_online_manager";
import { AdminPartyManager } from "./admin_party_manager";
import { AdminTabs } from "./admin_tabs";
import { AdminTicketsManager } from "./admin_tickets_manager";
import { Messages } from "./messages";
import { Navbar } from "./navbar";
import { OfflineIndicator } from "./offline_indicator";

export function AdminLayout({ state }) {
  const { pathname } = useLocation();

  return (
    <div className="admin-root">
      <Navbar state={state} mode="admin" />
      <OfflineIndicator offline={state.offline && state.loaded} />
      <br />
      <div className="container">
        <Messages messages={state.messages} />
        <AdminTabs
          currentTab={pathname.split("/")[pathname.split("/").length - 1]}
          partyAlias={state.config.party_name}
        />
        <Routes>
          <Route index element={<AdminConfigManager state={state} />} />
          <Route
            path="tickets/*"
            element={<AdminTicketsManager state={state} />}
          />
          <Route
            path="assignments/*"
            element={<AdminAssignmentsManager state={state} />}
          />
          <Route
            path="locations/*"
            element={<AdminLocationsManager state={state} />}
          />
          <Route
            path="online/*"
            element={<AdminOnlineManager state={state} />}
          />
          <Route path="party/*" element={<AdminPartyManager state={state} />} />
        </Routes>
      </div>
    </div>
  );
}
