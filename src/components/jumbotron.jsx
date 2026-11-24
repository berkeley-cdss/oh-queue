import { loginPath } from "../common";
import { Messages } from "./messages";
import { RequestForm } from "./request_form";

export let Jumbotron = ({ state }) => {
  var isQueueOpen = state.config && JSON.parse(state.config.is_queue_open);
  const party_enabled = state.config.party_enabled;
  let titleText, subtitleText, contents;
  if (!state.currentUser) {
    titleText = "Hi! Please sign in";
    subtitleText = "Sign in with your bCourse account to request help";
    contents = (
      <a className="btn btn-block btn-jumbo btn-outline" href={loginPath()}>
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
    <div className="jumbotron blue">
      <div className="container">
        <section className="page-header">
          <div className="row">
            <Messages messages={state.messages} />
          </div>
          <div className="row">
            <div className="col-md-7 col-lg-8">
              <h3 className="truncate">{titleText}</h3>
              <p className="truncate">{subtitleText}</p>
            </div>
            <div className="col-md-5 col-lg-4">
              <div className="request-form">{contents}</div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};
