import { Markdown } from "./markdown";
import { ConfigLinked } from "./config_linked_form";

export function ConfigLinkedMarkdownInput({
  title,
  placeholder,
  config,
  configKey,
}) {
  return (
    <ConfigLinked
      configKey={configKey}
      config={config}
      render={({ onSubmit, onChange, value, submitButton }) => (
        <form onSubmit={onSubmit}>
          <div className="form-group">
            <label>{title} (supports Markdown)</label>
            <textarea
              className="form-control"
              name="ticket-input"
              placeholder={placeholder}
              value={value}
              onChange={onChange}
            />
          </div>
          <label>{title} Preview:</label>
          <div
            className="alert alert-info alert-dismissable fade in"
            role="alert"
          >
            <button
              type="button"
              className="close"
              aria-label="Close"
              data-dismiss="alert"
            >
              <span aria-hidden="true">&times;</span>
            </button>
            <Markdown>{value}</Markdown>
          </div>
          <div className="form-group">
            <div>{submitButton}</div>
          </div>
        </form>
      )}
    />
  );
}
