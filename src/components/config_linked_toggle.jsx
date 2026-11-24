import { app } from "../app_instance";
import { ConfigLinked } from "./config_linked_form";
import { FancyToggle } from "./fancy_toggle";

export function ConfigLinkedToggle({
  config,
  configKey,
  label,
  offText = "No",
  onText = "Yes",
}) {
  if (!app || Object.keys(config).length === 0) {
    return null;
  }
  return (
    <ConfigLinked
      configKey={configKey}
      config={config}
      render={({ onSubmit, value }) => (
        <FancyToggle
          checked={value === "true" || value === true}
          label={label}
          offText={offText}
          onText={onText}
          onChange={(x) => onSubmit(x ? "true" : "false")}
        />
      )}
    />
  );
}
