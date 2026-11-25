import React from "react";
import { app } from "../app_instance";
import { Navbar } from "./navbar";
import { NotFound } from "./not_found";
import { OfflineIndicator } from "./offline_indicator";

export function StaffOnlineSetup({ state }) {
  // While a save is in flight, the button shows it and can't be pressed again.
  const [saving, setSaving] = React.useState(false);

  if (!state.currentUser || !state.currentUser.isStaff) {
    return <NotFound />;
  }

  const submit = (e) => {
    e.preventDefault();
    const formData = Object.fromEntries(new FormData(e.currentTarget));
    setSaving(true);
    // Shown for at least a quarter of a second, so it doesn't just flicker.
    const minimumTime = new Promise((resolve) => setTimeout(resolve, 250));
    app
      .makeRequest("update_staff_online_setup", formData)
      .then(() => minimumTime)
      .then(() => setSaving(false));
  };

  return (
    <div>
      <Navbar state={state} mode="online_setup" />
      <OfflineIndicator offline={state.offline && state.loaded} />
      <main>
        <div className="container">
          <br />
          <p id="online-setup-scope">
            These links are yours in <strong>every course</strong> you staff on
            the Office Hours Queue, not just {window.courseName}: changing them
            here changes them in all of your courses.
          </p>
          <p>
            Consider using <a href="https://meet.google.com">Google Meet</a> to
            host video calls.
          </p>
          <form id="staff-online-setup-form" onSubmit={submit}>
            <div className="mb-3">
              <label className="form-label" htmlFor="staff-call-link">
                Your Default Video Call Link (all courses)
              </label>
              <input
                type="text"
                className="form-control"
                id="staff-call-link"
                aria-describedby="online-setup-scope"
                name="staff-call-link"
                placeholder="meet.google.com/xyz"
                defaultValue={state.currentUser.call_url}
              />
            </div>
            <div className="mb-3">
              <label className="form-label" htmlFor="staff-doc-link">
                Your Default Shared Document Link (all courses)
              </label>
              <input
                type="text"
                className="form-control"
                id="staff-doc-link"
                aria-describedby="online-setup-scope"
                name="staff-doc-link"
                placeholder="docs.google.com/xyz"
                defaultValue={state.currentUser.doc_url}
              />
            </div>
            <button
              id="submitBtn"
              type="submit"
              className={
                saving ? "btn btn-primary is-loading" : "btn btn-primary"
              }
              disabled={saving}
            >
              Submit
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
