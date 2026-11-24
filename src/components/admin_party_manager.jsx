import React from "react";
import { AdminOptionsManager } from "./admin_options_manager";
import { ConfigLinkedText } from "./config_linked_text";
import { ConfigLinkedToggle } from "./config_linked_toggle";

export function AdminPartyManager({ state }) {
  return (
    <React.Fragment>
      <AdminOptionsManager>
        <tr>
          <td>What should {state.config.party_name} mode be called?</td>
          <td className="col-md-1">
            <ConfigLinkedText
              config={state.config}
              configKey="party_name"
              label="Name of the party queue"
            />
          </td>
        </tr>
        <tr>
          <td>
            Should students be able to create and join {state.config.party_name}{" "}
            groups?
          </td>
          <td className="col-md-1">
            <ConfigLinkedToggle
              config={state.config}
              configKey="party_enabled"
              label="Students can create and join groups"
            />
          </td>
        </tr>
        <tr>
          <td>
            Should students be able to create individual tickets while{" "}
            {state.config.party_name} mode is enabled?
          </td>
          <td className="col-md-1">
            <ConfigLinkedToggle
              config={state.config}
              configKey="allow_private_party_tickets"
              label="Individual tickets allowed in group mode"
            />
          </td>
        </tr>
      </AdminOptionsManager>
    </React.Fragment>
  );
}
