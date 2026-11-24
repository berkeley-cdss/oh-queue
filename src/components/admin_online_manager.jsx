import { AdminOptionsManager } from "./admin_options_manager";
import { ConfigLinkedToggle } from "./config_linked_toggle";

export function AdminOnlineManager({ state }) {
  return (
    <AdminOptionsManager>
      <tr>
        <td>Should students be able to join an online queue?</td>
        <td className="col-md-1">
          <ConfigLinkedToggle
            config={state.config}
            configKey="online_active"
            label="Online queue"
            offText="No"
            onText="Yes"
          />
        </td>
      </tr>
      <tr>
        <td>
          Should students or TAs specify the video call link for an online OH
          call?
        </td>
        <td className="col-md-1">
          <ConfigLinkedToggle
            config={state.config}
            configKey="students_set_online_link"
            label="Who sets the video call link"
            offText="TAs"
            onText="Students"
          />
        </td>
      </tr>
      <tr>
        <td>
          Should students or TAs specify the shared document link for an online
          OH call?
        </td>
        <td className="col-md-1">
          <ConfigLinkedToggle
            config={state.config}
            configKey="students_set_online_doc"
            label="Who sets the shared document link"
            offText="TAs"
            onText="Students"
          />
        </td>
      </tr>
    </AdminOptionsManager>
  );
}
