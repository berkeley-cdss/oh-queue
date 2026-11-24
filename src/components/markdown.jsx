import { characterEntitiesLegacy } from "character-entities-legacy";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Longest first, so a reference uses the longest name it starts with, as in HTML.
const LEGACY_NAMES = [...characterEntitiesLegacy].sort(
  (a, b) => b.length - a.length,
);

// Code, where references aren't decoded: fenced blocks, then inline spans,
// which end at a run of as many backticks as they start with.
const CODE = /```[\s\S]*?```|~~~[\s\S]*?~~~|(`+)[\s\S]*?\1(?!`)/g;

// react-markdown 4, which the queue used before, decoded character references
// without their semicolon, as browsers do (`&nbsp`, `&copy`, `&#160`), and
// course staff wrote messages that way. CommonMark needs the semicolon, so this
// adds it, outside code, leaving references that already have one alone.
function terminateReferences(text) {
  let result = "";
  let end = 0;
  for (const code of text.matchAll(CODE)) {
    result += terminateIn(text.slice(end, code.index)) + code[0];
    end = code.index + code[0].length;
  }
  return result + terminateIn(text.slice(end));
}

function terminateIn(text) {
  return text.replace(
    /&(#[xX][0-9a-fA-F]+|#[0-9]+|[A-Za-z][A-Za-z0-9]*)(;?)/g,
    (reference, name, semicolon) => {
      if (semicolon) {
        return reference;
      }
      if (name.startsWith("#")) {
        return `&${name};`;
      }
      const legacy = LEGACY_NAMES.find((legacyName) =>
        name.startsWith(legacyName),
      );
      return legacy ? `&${legacy};${name.slice(legacy.length)}` : reference;
    },
  );
}

// Markdown that course staff write in the settings, GitHub-flavored as it was
// with react-markdown 4.
export function Markdown({ children }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]}>
      {children == null ? children : terminateReferences(children)}
    </ReactMarkdown>
  );
}
