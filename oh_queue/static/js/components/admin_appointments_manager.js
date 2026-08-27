function AdminAppointmentsManager({ state }) {
  const [sheetUrl, setSheetUrl] = React.useState("");
  const [sheetName, setSheetName] = React.useState("");

  const [isLoading, setIsLoading] = React.useState(false);

  const handleSheetUrlChange = (e) => {
    setSheetUrl(e.target.value);
  };
  const handleSheetNameChange = (e) => {
    setSheetName(e.target.value);
  };

  const submit = () => {
    setIsLoading(true);
    app.makeRequest(
      "upload_appointments",
      {
        sheetUrl,
        sheetName,
      },
      false,
      () => {
        setIsLoading(false);
      }
    );
  };

  return (
    <React.Fragment>
      <AdminOptionsManager>
        <tr>
          <td>Should students be able to make appointments?</td>
          <td className="col-md-1">
            <ConfigLinkedToggle
              config={state.config}
              configKey="appointments_open"
              offText="No"
              onText="Yes"
            />
          </td>
        </tr>
        <tr>
          <td>What should appointments be called for students?</td>
          <td className="col-md-1">
            <ConfigLinkedText
              config={state.config}
              configKey="appointment_mode_title"
            />
          </td>
        </tr>
        <tr>
          <td>
            Should students be prompted to make appointments when the queue
            closes?
          </td>
          <td className="col-md-1">
            <ConfigLinkedToggle
              config={state.config}
              configKey="recommend_appointments"
              offText="No"
              onText="Yes"
            />
          </td>
        </tr>
        <tr>
          <td>
            <p>How many appointments should a student be able to make daily?</p>
          </td>
          <td className="col-md-3">
            <ConfigLinkedNumeric
              config={state.config}
              configKey="daily_appointment_limit"
            />
          </td>
        </tr>
        <tr>
          <td>
            <p>
              How many appointments should a student be able to make weekly?
            </p>
          </td>
          <td className="col-md-3">
            <ConfigLinkedNumeric
              config={state.config}
              configKey="weekly_appointment_limit"
            />
          </td>
        </tr>
        <tr>
          <td>
            <p>
              How many appointments should a student have be pending
              simultaneously?
            </p>
          </td>
          <td className="col-md-3">
            <ConfigLinkedNumeric
              config={state.config}
              configKey="simul_appointment_limit"
            />
          </td>
        </tr>
        <tr>
          <td>
            Should appointments be activated automatically?
          </td>
          <td className="col-md-1">
            <ConfigLinkedToggle
              config={state.config}
              configKey="auto_activate_appointments"
              offText="No"
              onText="Yes"
            />
          </td>
        </tr>
        <tr>
          <td>
            <p>
              How often should appointments be activated (in hours)?
            </p>
          </td>
          <td className="col-md-3">
            <ConfigLinkedNumeric
              config={state.config}
              configKey="auto_activate_appointments_frequency"
            />
          </td>
        </tr>
        <tr>
          <td>
            <p>
              How many hours of appointments should be activated each time?
            </p>
          </td>
          <td className="col-md-3">
            <ConfigLinkedNumeric
              config={state.config}
              configKey="auto_activate_appointments_range"
            />
          </td>
        </tr>
        <tr>
          <td>
            Should students always have access to online appointment call links?
          </td>
          <td className="col-md-1">
            <ConfigLinkedToggle
              config={state.config}
              configKey="always_show_appointment_join_call"
              offText="No"
              onText="Yes"
            />
          </td>
        </tr>
      </AdminOptionsManager>
      <ConfigLinkedMarkdownInput
        title="Appointment Prompt"
        placeholder="Sign up for appointments here!"
        config={state.config}
        configKey="appointment_prompt"
      />
      <form>
        <div className="input-group appointment-input">
          <input
            id="url-selector"
            type="text"
            className="form-control"
            placeholder="Link to a spreadsheet containing appointments"
            required
            value={sheetUrl}
            onChange={handleSheetUrlChange}
          />
          <input
            id="sheet-selector"
            className="form-control form-right"
            type="text"
            name="question"
            title="Sheet name"
            placeholder="Sheet name"
            required
            value={sheetName}
            onChange={handleSheetNameChange}
          />
          <span className="input-group-btn">
            <button
              className={"btn btn-default " + (isLoading ? "is-loading" : "")}
              type="button"
              onClick={submit}
            >
              Update
            </button>
          </span>
        </div>
        <small>
          You must share this spreadsheet with the 61A service account{" "}
          <a href="mailto:secure-links@ok-server.iam.gserviceaccount.com">
            secure-links@ok-server.iam.gserviceaccount.com
          </a>
          .
        </small>
      </form>
    </React.Fragment>
  );
}
