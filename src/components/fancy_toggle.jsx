import React from "react";
import Form from "react-bootstrap/Form";

// A Bootstrap switch, showing onText/offText for its current state, as in sections'
// ToggleSwitch. label names the setting for screen readers.
export function FancyToggle({ checked, onChange, offText, onText, label }) {
  const id = React.useId();
  const [on, setOn] = React.useState(checked);
  // Follow checked when it changes, e.g. after the server's config reloads.
  const [prevChecked, setPrevChecked] = React.useState(checked);
  if (checked !== prevChecked) {
    setPrevChecked(checked);
    setOn(checked);
  }

  return (
    <Form.Check
      type="switch"
      role="switch"
      id={id}
      checked={on}
      label={
        <>
          <span className="visually-hidden">{label}: </span>
          {on ? onText : offText}
        </>
      }
      onChange={(e) => {
        setOn(e.target.checked);
        onChange(e.target.checked);
      }}
    />
  );
}
