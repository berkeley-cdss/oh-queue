import React from "react";
import { SelectPicker } from "./select_picker";

export function UpdateAssignmentBox({ state, elem, onSubmit }) {
  const { assignments } = state;

  let filteredAssignments = Object.values(assignments)
    .filter((assignment) => assignment.visible)
    .sort((a, b) => a.name.localeCompare(b.name));

  const [assignment_id, setAssignment] = React.useState(elem.assignment_id);
  const [question, setQuestion] = React.useState(elem.question);

  return (
    <div className="update-assignment">
      <div className="input-group input-group-lg">
        <SelectPicker
          options={filteredAssignments}
          value={assignment_id}
          onChange={(e) => setAssignment(parseInt(e.target.value))}
          className="form-left"
          id="assignment_id"
          name="assignment_id"
          title="Assignment"
          required
        />
        <input
          className="form-control form-right"
          type="text"
          id="question"
          name="question"
          aria-label="Question"
          placeholder="Question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
      </div>
      {assignment_id !== elem.assignment_id || question !== elem.question ? (
        <button
          type="button"
          onClick={() => onSubmit({ assignment_id, question })}
          className="description-button btn btn-primary btn-lg w-100"
        >
          Update Assignment
        </button>
      ) : null}
    </div>
  );
}
