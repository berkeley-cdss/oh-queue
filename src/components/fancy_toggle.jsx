import React from "react";

// A checkbox shown as an on/off switch by the bootstrap-toggle jQuery plugin.
export function FancyToggle({ checked, onChange, offText, onText }) {
  const inputRef = React.useRef(null);
  // The latest onChange, for the plugin's change handler.
  const onChangeRef = React.useRef(onChange);
  React.useEffect(() => {
    onChangeRef.current = onChange;
  });

  React.useEffect(() => {
    $(inputRef.current).bootstrapToggle();
  }, []);

  // Show checked without reporting it as a change, then listen for the person's.
  React.useEffect(() => {
    const toggle = inputRef.current;
    $(toggle).off("change");
    $(toggle).bootstrapToggle(checked ? "on" : "off");
    $(toggle).change(() => onChangeRef.current(toggle.checked));
  }, [checked]);

  return (
    <input
      ref={inputRef}
      type="checkbox"
      defaultChecked={checked}
      data-off={offText}
      data-on={onText}
      data-size="mini"
      data-toggle="toggle"
    />
  );
}
