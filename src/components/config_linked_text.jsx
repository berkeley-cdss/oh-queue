import React from "react";
import { ConfigLinked } from "./config_linked_form";

export function ConfigLinkedText({
  config,
  configKey,
  lines = 1,
  placeholder,
  title,
  label,
  optional,
}) {
  const id = React.useId();
  const Input = lines > 1 ? "textarea" : "input";
  return (
    <ConfigLinked
      configKey={configKey}
      config={config}
      render={({ onSubmit, onChange, value, submitButton }) => (
        <form onSubmit={onSubmit}>
          <div className="mb-3">
            {title && (
              <label className="form-label fw-bold" htmlFor={id}>
                {title}
              </label>
            )}
            <Input
              id={id}
              type="text"
              className="form-control"
              aria-label={title ? undefined : label}
              required={optional ? undefined : "required"}
              value={value}
              onChange={onChange}
              placeholder={placeholder}
              rows={lines}
            />
          </div>
          {submitButton}
        </form>
      )}
    />
  );
}
