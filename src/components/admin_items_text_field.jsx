import React from "react";
import { app } from "../app_instance";

export function AdminItemsTextField({ itemType, placeholder, propType, item }) {
  const [saving, setSaving] = React.useState(false);
  const editItem = (e) => {
    e.preventDefault();
    const value = e.currentTarget.elements[0].value;
    setSaving(true);
    app
      .makeRequest(`update_${itemType}`, { id: item.id, [propType]: value })
      .then(() => setSaving(false));
  };

  return (
    <form onSubmit={editItem}>
      <div className="input-group input-group-sm">
        <input
          className="form-control"
          type="text"
          aria-label={`${placeholder} of ${itemType} ${item.id}`}
          placeholder={placeholder}
          data-item-id={item.id}
          defaultValue={item[propType]}
        />
        <button
          className={
            saving
              ? "btn btn-outline-secondary is-loading"
              : "btn btn-outline-secondary"
          }
          type="submit"
          disabled={saving}
        >
          Edit
        </button>
      </div>
    </form>
  );
}
