import React from "react";
import { app } from "../app_instance";

export function ConfigLinked({ configKey, configKeys = [], config, render }) {
  const [value, setValue] = React.useState(config[configKey]);
  const [values, setValues] = React.useState(
    configKeys.map((key) => config[key]),
  );
  // While a save is in flight, the button shows it and can't be pressed again.
  const [saving, setSaving] = React.useState(false);

  // Start over from the saved settings whenever they change.
  const saved = [config[configKey], ...configKeys.map((key) => config[key])];
  const [shown, setShown] = React.useState(saved);
  if (
    saved.length !== shown.length ||
    saved.some((savedValue, i) => savedValue !== shown[i])
  ) {
    setShown(saved);
    setValue(saved[0]);
    setValues(saved.slice(1));
  }

  const setters = configKeys.map(
    (key, i) => (val) =>
      setValues((values) =>
        values
          .slice(0, i)
          .concat([val])
          .concat(values.slice(i + 1)),
      ),
  );
  const handlers = setters.map((setter) => (e) => setter(e.target.value));

  const handleSubmit = (e) => {
    if (e.preventDefault) {
      e.preventDefault();
    }
    setSaving(true);
    // Shown for at least a quarter of a second, so it doesn't just flicker.
    const minimumTime = new Promise((resolve) => setTimeout(resolve, 250));

    const requestBody = configKey
      ? { key: configKey, value: e.target ? value : e }
      : { keys: configKeys, values };

    // Whether or not it worked: a failed save shows the offline banner, and can be tried again.
    app
      .makeRequest(`update_config`, requestBody)
      .then(() => minimumTime)
      .then(() => setSaving(false));

    return false;
  };

  const submitButton = (
    <button
      className={
        saving
          ? "btn btn-outline-secondary is-loading"
          : "btn btn-outline-secondary"
      }
      name="btn-submit"
      type="submit"
      disabled={saving}
    >
      Save
    </button>
  );

  const onChange = (e) => setValue(e.target.value);

  return render({
    onSubmit: handleSubmit,
    onChange,
    value,
    setValue,
    submitButton,
    values,
    setters,
    handlers,
  });
}
