import classNames from "classnames";
import React from "react";
import { app } from "../app_instance";

export function AdminItemsManager({ children, columns, itemType, items }) {
  const [input, setInput] = React.useState("");
  const [isLoading, setIsLoading] = React.useState(false);

  const isValidInput = input
    ? !items.map((item) => item.name).includes(input)
    : null;

  const onChange = (input) => {
    setInput(input);
  };

  const addItemInput = () => {
    if (!isValidInput) {
      return;
    }

    setIsLoading(true);

    app.makeRequest(`add_${itemType}`, { name: input }, (success) => {
      setIsLoading(false);
      if (success) {
        setInput("");
      }
    });
  };

  const inputClassNames = classNames("form-control", {
    "is-invalid": isValidInput === false,
    "is-valid": isValidInput === true,
  });

  return (
    <div className="table-responsive">
      <table className="table table-hover">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>
                <span>{column}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              {children(item).map((child, i) => (
                <td key={i}>{child}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <table className="table table-hover">
        <tbody>
          <tr key="new">
            <td>
              <div>
                <input
                  className={inputClassNames}
                  type="text"
                  minLength="1"
                  aria-label={`Name of a new ${itemType}`}
                  placeholder="Add new entry"
                  disabled={isLoading}
                  value={input}
                  onChange={(e) => onChange(e.target.value)}
                />
              </div>
            </td>
            <td className="admin-add-button">
              <button
                type="button"
                className="btn btn-outline-secondary"
                disabled={!isValidInput || isLoading}
                onClick={addItemInput}
              >
                {isLoading ? (
                  <span
                    className="spinner-border spinner-border-sm"
                    role="status"
                    aria-label="Adding"
                  />
                ) : (
                  "Add"
                )}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
