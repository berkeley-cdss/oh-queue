import { ConfigLinked } from "./config_linked_form";

// label names the field, for screen readers.
export function ConfigLinkedNumeric({ config, configKey, label }) {
  return (
    <ConfigLinked
      configKey={configKey}
      config={config}
      render={({ onSubmit, onChange, value, submitButton }) => (
        <form onSubmit={onSubmit}>
          <div className="mb-3">
            <input
              type="number"
              className="form-control"
              aria-label={label}
              required="required"
              value={value}
              onChange={onChange}
            />
          </div>
          {submitButton}
        </form>
      )}
    />
  );
}
