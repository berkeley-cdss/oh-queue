import Alert from "react-bootstrap/Alert";
import { app } from "../app_instance";

export let Messages = ({ messages }) => (
  <div className="messages">
    {messages.map((message) => (
      <Message key={message.id} message={message} />
    ))}
  </div>
);

export let Message = ({ message }) => {
  let { id, text, category, visible } = message;
  if (!visible) {
    return null;
  }
  return (
    <Alert
      variant={category}
      dismissible
      closeLabel="Dismiss"
      onClose={() => app.clearMessage(id)}
    >
      {text}
    </Alert>
  );
};
