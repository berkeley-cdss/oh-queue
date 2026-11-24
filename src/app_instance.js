// The one and only App (components/app.jsx), which holds the page's state. Components
// call its methods, such as app.makeRequest, to talk to the server and update the state.
export let app = null;

export function setApp(instance) {
  app = instance;
}
