import React from "react";
import { app } from "../app_instance";
import { SelectPicker } from "./select_picker";

// Staff narrow the queue to an assignment, a question and a location.
export function FilterControls({ state }) {
  const [filter, setFilter] = React.useState({
    assignment_id: "",
    question: "",
    location_id: "",
  });
  const update = (key) => (e) => {
    const next = { ...filter, [key]: e.target.value };
    setFilter(next);
    app.setFilter({ ...next });
  };

  let { assignments, locations } = state;
  let sortedAssignments = Object.values(assignments).sort((a, b) =>
    a.name.localeCompare(b.name),
  );
  let sortedLocations = Object.values(locations).sort((a, b) =>
    a.name.localeCompare(b.name),
  );

  return (
    <div className="row g-3 filter-controls">
      <div className="col-12 col-sm-4">
        <SelectPicker
          options={sortedAssignments}
          emptyOption="Any Assignment"
          size="lg"
          id="assignment"
          name="assignment"
          title="Filter by assignment"
          value={filter.assignment_id}
          onChange={update("assignment_id")}
        />
      </div>
      <div className="col-12 col-sm-4">
        <input
          className="form-control form-control-lg"
          type="text"
          id="question"
          name="question"
          aria-label="Filter by question"
          placeholder="Question"
          value={filter.question}
          onChange={update("question")}
        />
      </div>
      <div className="col-12 col-sm-4">
        <SelectPicker
          options={sortedLocations}
          emptyOption="Any Location"
          size="lg"
          id="location"
          name="location"
          title="Filter by location"
          value={filter.location_id}
          onChange={update("location_id")}
        />
      </div>
    </div>
  );
}
