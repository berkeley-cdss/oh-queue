import { useNavigate } from "react-router-dom";
import React from "react";
import Modal from "react-bootstrap/Modal";
import { app } from "../app_instance";
import { SelectPicker } from "./select_picker";

export function RequestForm(props) {
  let state = props.state;
  const forceTicket = props.forceTicket;
  let party_enabled = state.config.party_enabled && !forceTicket;
  const is_queue_open =
    JSON.parse(state.config.is_queue_open) &&
    (!party_enabled || state.config.allow_private_party_tickets);
  const disabled = !party_enabled && !is_queue_open;
  let descriptionRequired = state.config.description_required === "true";

  const formRef = React.useRef(null);
  // Asking for a description, when the course requires one, before sending the request.
  const [describing, setDescribing] = React.useState(false);
  const [description, setDescription] = React.useState(
    state.config.default_description || "",
  );

  const send = () => {
    const formData = Object.fromEntries(new FormData(formRef.current));
    formData["description"] = description;
    app.makeRequest(party_enabled ? "create_group" : "create", formData, true);
    setDescribing(false);
  };

  const onSubmit = (e) => {
    e.preventDefault();
    if (!descriptionRequired || party_enabled) {
      send();
    } else {
      setDescribing(true);
    }
  };

  const navigate = useNavigate();

  const openAlternative = () => navigate("/queue");

  let { assignments, locations } = state;

  let filteredAssignments = Object.values(assignments)
    .filter((assignment) => assignment.visible)
    .sort((a, b) => a.name.localeCompare(b.name));
  let filteredLocations = Object.values(locations)
    .filter((location) => location.visible)
    .sort((a, b) => a.name.localeCompare(b.name));

  let magicWordInput = false;
  if (
    state.config &&
    !party_enabled &&
    state.config.queue_magic_word_mode &&
    state.config.queue_magic_word_mode !== "none"
  ) {
    magicWordInput = (
      <div className="mb-3">
        <input
          className="form-control form-control-lg"
          type="password"
          id="magic-word"
          name="magic_word"
          aria-label="Magic Word"
          placeholder="Magic Word"
          required
          disabled={disabled}
        />
      </div>
    );
  }

  const [locationID, setLocationID] = React.useState(null);

  const handleLocationChange = (e) => {
    setLocationID(e.target.value);
  };

  const showOnlineInput = locationID && state.locations[locationID].online;
  const linkKnown = locationID && state.locations[locationID].link;

  return (
    <div>
      <form id="request-form" ref={formRef} onSubmit={onSubmit}>
        {magicWordInput}
        <div className="input-group input-group-lg mb-3">
          <SelectPicker
            options={filteredAssignments}
            placeholder="Assignment"
            className="form-left"
            id="assignment_id"
            name="assignment_id"
            title="Assignment"
            required
            disabled={disabled}
          />
          <input
            className="form-control form-right"
            type="text"
            id="question"
            name="question"
            aria-label="Question"
            placeholder="Question"
            required
            disabled={disabled}
          />
        </div>
        {showOnlineInput && (
          <React.Fragment>
            {(party_enabled ||
              state.locations[locationID].name !== "Online" ||
              JSON.parse(state.config.students_set_online_link)) && (
              <div className="mb-3">
                <label className="form-label" htmlFor="call-link">
                  {linkKnown ? "Breakout Room (optional)" : "Video Call Link"}
                </label>
                <input
                  className="form-control form-control-lg"
                  type="text"
                  id="call-link"
                  name="call-link"
                  title="Video Call Link"
                  placeholder={
                    linkKnown ? "Breakout Room 6" : "meet.google.com/xyz"
                  }
                  required={!linkKnown}
                  disabled={disabled}
                />
              </div>
            )}
            {(party_enabled ||
              JSON.parse(state.config.students_set_online_doc)) && (
              <div className="mb-3">
                <label className="form-label" htmlFor="doc-link">
                  Shared Document Link (optional)
                </label>
                <input
                  className="form-control form-control-lg"
                  type="text"
                  id="doc-link"
                  name="doc-link"
                  title="Shared Doc Link"
                  placeholder="docs.google.com/xyz"
                  disabled={disabled}
                />
              </div>
            )}
          </React.Fragment>
        )}
        <div className="input-group input-group-lg mb-3">
          <SelectPicker
            options={filteredLocations}
            placeholder="Location"
            className="form-left"
            id="location_id"
            name="location_id"
            title="Location"
            required
            onChange={handleLocationChange}
            disabled={disabled}
          />
          <button
            type="submit"
            className="btn btn-primary form-right"
            disabled={disabled}
          >
            {party_enabled ? "Create" : "Request"}
          </button>
        </div>
        {party_enabled && is_queue_open && (
          <button
            type="button"
            className="btn btn-outline-primary btn-lg w-100"
            onClick={openAlternative}
          >
            Or ask staff privately
          </button>
        )}
      </form>
      <Modal show={describing} onHide={() => setDescribing(false)} centered>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <Modal.Header closeButton closeLabel="Cancel">
            <Modal.Title as="h2" className="h4">
              <label htmlFor="description-box">
                Please describe your issue below:
              </label>
            </Modal.Title>
          </Modal.Header>
          <Modal.Body>
            <textarea
              id="description-box"
              className="form-control description-box"
              rows="5"
              required
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={
                state.config.default_description ||
                'It would be helpful if you could describe your issue. For example, "I have a SyntaxError in my ___ function. I\'ve tried using ____ and ____."'
              }
            />
          </Modal.Body>
          <Modal.Footer>
            <button type="submit" className="btn btn-primary btn-lg">
              Request
            </button>
          </Modal.Footer>
        </form>
      </Modal>
    </div>
  );
}
