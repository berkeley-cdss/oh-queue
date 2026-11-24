import { app } from "../app_instance";
import { FancyToggle } from "./fancy_toggle";

export function AdminItemsBooleanField({
  itemType,
  propType,
  item,
  label,
  onText = "Yes",
  offText = "No",
}) {
  const handleChange = (value) => {
    app.makeRequest(`update_${itemType}`, { id: item.id, [propType]: value });
  };

  return (
    <FancyToggle
      onText={onText}
      offText={offText}
      label={label}
      checked={item[propType]}
      onChange={handleChange}
    />
  );
}
