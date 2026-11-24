import React from "react";
import { app } from "../app_instance";
import { SelectPicker } from "./select_picker";
import { isStaff } from "../state";

// For a student who has moved: changes their ticket's location.
export function UpdateLocationBox({ state, ticket }) {
  const id = React.useId();
  const [locationId, setLocationId] = React.useState("");
  let filteredLocations = Object.values(state.locations)
    .filter((location) => location.visible)
    .sort((a, b) => a.name.localeCompare(b.name));
  if (isStaff(state)) {
    return null;
  }
  const submit = () => {
    app.makeRequest("update_ticket", {
      id: ticket.id,
      location_id: locationId,
    });
  };
  return (
    <div>
      <label htmlFor={id} className="form-label h5">
        If you have moved, please update your new location here:
      </label>
      <div className="input-group input-group-lg">
        <SelectPicker
          id={id}
          options={filteredLocations}
          placeholder="Location"
          name="location"
          value={locationId}
          onChange={(e) => setLocationId(e.target.value)}
        />
        <button
          type="button"
          className="btn btn-outline-primary"
          onClick={submit}
          disabled={!locationId || locationId == ticket.location_id}
        >
          Update
        </button>
      </div>
    </div>
  );
}
