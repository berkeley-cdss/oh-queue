import React from "react";
import { isStaff } from "../state";

export function DescriptionBox({
  editable,
  locked,
  state,
  ticket,
  prompt,
  placeholder,
  description,
  onChange,
  onSubmit,
}) {
  const id = React.useId();
  let staff = isStaff(state);

  if ((!editable && staff) || locked) {
    return (
      <p className="ticket-view-desc">
        {ticket.description ? ticket.description : <i>No description</i>}
      </p>
    );
  } else {
    return (
      <div>
        <label htmlFor={id} className="form-label h5">
          {prompt}
        </label>
        <textarea
          id={id}
          className="form-control description-box"
          value={description || ""}
          onChange={(e) => onChange(e.target.value)}
          rows="5"
          placeholder={placeholder}
        />
        {description !== ticket.description ? (
          <button
            type="button"
            onClick={onSubmit}
            className="description-button btn btn-primary btn-lg w-100"
          >
            Save Description
          </button>
        ) : null}
      </div>
    );
  }
}
