import { loginPath } from "../common";
import { Messages } from "./messages";
import { RequestForm } from "./request_form";

// The banner at the top of the queue for students: a greeting, and the form for
// asking for help (or a sign-in button).
export let Jumbotron = ({ state }) => {
  var isQueueOpen = state.config && JSON.parse(state.config.is_queue_open);
  const party_enabled = state.config.party_enabled;
  let titleText, subtitleText, contents;
  if (!state.currentUser) {
    titleText = "Hi! Please sign in";
    subtitleText = "Sign in with your bCourses account to request help";
    contents = (
      <a className="btn btn-primary btn-lg w-100" href={loginPath()}>
        Sign in with bCourses
      </a>
    );
  } else if (!isQueueOpen) {
    titleText = `Hello, ${state.currentUser.shortName}`;
    subtitleText = "The queue is currently closed. Check back later!";
    contents = <RequestForm state={state} />;
  } else {
    titleText = `Hello, ${state.currentUser.shortName}`;
    subtitleText = "Fill out the form to request help!";
    contents = <RequestForm state={state} />;
  }

  if (state.currentUser && party_enabled) {
    subtitleText = "Join an existing group, or create a new one!";
  }

  return (
    <div className="hero">
      <div className="container">
        <Messages messages={state.messages} />
        <div className="row g-4 align-items-center">
          <div className="col-md-6 col-lg-7">
            <h2>{titleText}</h2>
            <p className="lead mb-0">{subtitleText}</p>
          </div>
          <div className="col-md-6 col-lg-5">
            <div className="request-form">{contents}</div>
          </div>
        </div>
      </div>
    </div>
  );
};
