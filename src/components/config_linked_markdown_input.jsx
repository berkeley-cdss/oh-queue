import React from "react";
import { Markdown } from "./markdown";
import { ConfigLinked } from "./config_linked_form";

export function ConfigLinkedMarkdownInput({
  title,
  placeholder,
  config,
  configKey,
}) {
  const id = React.useId();
  return (
    <ConfigLinked
      configKey={configKey}
      config={config}
      render={({ onSubmit, onChange, value, submitButton }) => (
        <form onSubmit={onSubmit}>
          <div className="mb-3">
            <label className="form-label fw-bold" htmlFor={id}>
              {title} (supports Markdown)
            </label>
            <textarea
              id={id}
              className="form-control"
              name="ticket-input"
              placeholder={placeholder}
              value={value}
              onChange={onChange}
            />
          </div>
          <p className="form-label fw-bold">{title} Preview:</p>
          <div className="alert alert-info markdown-preview">
            <Markdown>{value}</Markdown>
          </div>
          <div className="mb-3">{submitButton}</div>
        </form>
      )}
    />
  );
}
