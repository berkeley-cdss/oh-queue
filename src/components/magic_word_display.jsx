import React from "react";
import { app } from "../app_instance";
import { isStaff } from "../state";

// How often a timed magic word is fetched again, since it changes.
const REFRESH_MS = 10000;

// For staff, the current magic word when it's a timed one, which they can't
// otherwise know. (Staff set a text magic word themselves.)
export function MagicWordDisplay({ state }) {
  const [magicWord, setMagicWord] = React.useState(undefined);
  const timed =
    state.loaded &&
    isStaff(state) &&
    state.config.queue_magic_word_mode === "timed_numeric";

  React.useEffect(() => {
    if (!timed) {
      return;
    }
    let stopped = false;
    const refresh = () =>
      app.makeRequest("refresh_magic_word", (res) => {
        if (!stopped && res) {
          setMagicWord(res.magic_word || null);
        }
      });
    refresh();
    const interval = setInterval(refresh, REFRESH_MS);
    return () => {
      stopped = true;
      clearInterval(interval);
    };
  }, [timed]);

  if (!timed || magicWord === undefined) {
    return false;
  }

  return (
    <div>
      <h4>
        Magic word: {magicWord ? <code>{magicWord}</code> : <i>Loading...</i>}
      </h4>
    </div>
  );
}
