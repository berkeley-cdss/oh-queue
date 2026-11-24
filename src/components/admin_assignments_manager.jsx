import { AdminItemsBooleanField } from "./admin_items_boolean_field";
import { AdminItemsManager } from "./admin_items_manager";
import { AdminItemsTextField } from "./admin_items_text_field";

export function AdminAssignmentsManager({ state }) {
  const { assignments } = state;

  return (
    <AdminItemsManager
      itemType="assignment"
      columns={["ID", "Name", "Visibility"]}
      items={Object.values(assignments)}
    >
      {(item) => [
        item.id,
        <AdminItemsTextField
          itemType="assignment"
          placeholder="New Name"
          propType="name"
          item={item}
        />,
        <AdminItemsBooleanField
          itemType="assignment"
          propType="visible"
          label={`${item.name} visibility`}
          item={item}
          onText="Visible"
          offText="Hidden"
        />,
      ]}
    </AdminItemsManager>
  );
}
