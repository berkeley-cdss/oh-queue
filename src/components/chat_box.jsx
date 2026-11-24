import moment from "moment";
import React from "react";
import { SendFill } from "react-bootstrap-icons";
import { app } from "../app_instance";
import { notifyUser } from "../common";

export function ChatBox({ currentUser, id, mode, messages }) {
  const [typed, setTyped] = React.useState("");
  const [numMessages, setNumMessages] = React.useState(0);
  const historyRef = React.useRef();

  const handleChange = (e) => {
    setTyped(e.target.value);
  };

  const postMessage = () => {
    if (!typed.trim()) {
      return;
    }
    app.makeRequest("send_chat_message", {
      content: typed,
      mode,
      id,
    });
    setTyped("");
  };

  const scrollDown = () => {
    historyRef.current.scrollTop = historyRef.current.scrollHeight;
  };

  React.useEffect(scrollDown, [messages]);

  function formatTooltip(message, omitUsername = false) {
    if (!message.created) return message.user.name;
    let time = moment.utc(message.created).local().format("ddd hh:mmA");
    if (omitUsername) return time;
    return `${message.user.name} | ${time}`;
  }

  if (messages.length != numMessages) {
    if (!document.hasFocus()) {
      const message = messages[messages.length - 1];
      notifyUser(
        "New Chat Message from " + message.user.shortName,
        message.body,
        null,
      );
    }
    setNumMessages(messages.length);
  }

  // Who sent each message and when: shown on hover, and read before it by screen readers.
  const bubble = (message, index, { mine, showIcon }) => {
    const { user, body } = message;
    const sender = mine ? "You" : user.name;
    return (
      <div key={index} className={mine ? "my-chat-bubble" : "chat-bubble"}>
        {!mine && (
          <div
            className={showIcon ? "chat-icon" : "chat-icon none"}
            aria-hidden="true"
          >
            {user.shortName[0]}
          </div>
        )}
        <div className="chat-text" title={formatTooltip(message, mine)}>
          <span className="visually-hidden">
            {message.created
              ? `${sender}, ${formatTooltip(message, true)}: `
              : `${sender}: `}
          </span>
          {body}
        </div>
      </div>
    );
  };

  const body = messages.map((message, i) =>
    bubble(message, i, {
      mine: message.user.id === currentUser.id,
      showIcon: !(
        messages[i + 1] && message.user.id === messages[i + 1].user.id
      ),
    }),
  );

  return (
    <section className="card chat-box" aria-labelledby={`chat-${mode}-${id}`}>
      <h2 className="card-header h6" id={`chat-${mode}-${id}`}>
        Chat
      </h2>
      <div className="card-body">
        <div className="chat-history" ref={historyRef} role="log">
          {body}
        </div>
        <form
          className="input-group chat-input"
          onSubmit={(e) => {
            e.preventDefault();
            postMessage();
          }}
        >
          <input
            type="text"
            className="form-control"
            aria-label="Message"
            placeholder="Type a message..."
            onChange={handleChange}
            value={typed}
          />
          <button
            className="btn btn-outline-secondary"
            type="submit"
            aria-label="Send"
          >
            <SendFill aria-hidden="true" />
          </button>
        </form>
      </div>
    </section>
  );
}
