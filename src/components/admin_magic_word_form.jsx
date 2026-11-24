import React from "react";
import { app } from "../app_instance";
import { ConfigLinked } from "./config_linked_form";

export function AdminMagicWordForm({ config }) {
  const [, setKey] = React.useState(0);
  const magicWordData = config["queue_magic_word_data"];

  React.useEffect(() => {
    if (!magicWordData) {
      app.makeRequest("refresh_magic_word", (res) => {
        if (res.magic_word) {
          config["queue_magic_word_data"] = res.magic_word;
          setKey((key) => key + 1);
        }
      });
    }
  }, [config, magicWordData]);

  return (
    <ConfigLinked
      configKeys={["queue_magic_word_mode", "queue_magic_word_data"]}
      config={config}
      render={({
        onSubmit,
        values: [mode, data],
        handlers: [onModeChange, onDataChange],
        setters: [, setData],
        submitButton,
      }) => (
        <InnerAdminMagicWordForm
          mode={mode}
          data={data}
          onModeChange={onModeChange}
          onDataChange={onDataChange}
          setData={setData}
          submitButton={submitButton}
          onSubmit={onSubmit}
        />
      )}
    />
  );
}

export function InnerAdminMagicWordForm({
  mode,
  data,
  onModeChange,
  onDataChange,
  setData,
  submitButton,
  onSubmit,
}) {
  const handleModeChange = (e) => {
    onModeChange(e);
    if (e.target.value === "text") {
      setData("");
    }
  };
  const queueMagicWordOptions = [
    <div className="mb-3" key="mode">
      <select
        className="form-select"
        aria-label="Type of magic word"
        value={mode}
        onChange={handleModeChange}
      >
        <option value="none">None</option>
        <option value="text">Text</option>
        <option value="timed_numeric">Time-based Numeric</option>
      </select>
    </div>,
  ];
  if (mode === "text") {
    queueMagicWordOptions.push(
      <div className="mb-3" key="data">
        <input
          type="text"
          className="form-control"
          aria-label="Magic word"
          value={data}
          onChange={onDataChange}
          required="required"
        />
      </div>,
    );
  }
  return (
    <form onSubmit={onSubmit}>
      {queueMagicWordOptions}
      {submitButton}
    </form>
  );
}
