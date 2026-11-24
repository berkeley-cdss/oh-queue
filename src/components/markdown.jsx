import { characterEntitiesLegacy } from "character-entities-legacy";
import { decodeNamedCharacterReference } from "decode-named-character-reference";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Longest first, so a reference uses the longest name it starts with, as in HTML.
const LEGACY_NAMES = [...characterEntitiesLegacy].sort(
  (a, b) => b.length - a.length,
);

// A character reference without its semicolon.
const UNTERMINATED = /&(#[xX][0-9a-fA-F]+|#[0-9]+|[A-Za-z][A-Za-z0-9]*)(;?)/g;

function decodeUnterminated(text) {
  return text.replace(UNTERMINATED, (reference, name, semicolon) => {
    if (semicolon) {
      return reference;
    }
    if (name.startsWith("#")) {
      const code =
        name[1] === "x" || name[1] === "X"
          ? parseInt(name.slice(2), 16)
          : parseInt(name.slice(1), 10);
      const valid =
        code > 0 && code <= 0x10ffff && !(code >= 0xd800 && code <= 0xdfff);
      return valid ? String.fromCodePoint(code) : "�";
    }
    const legacy = LEGACY_NAMES.find((legacyName) =>
      name.startsWith(legacyName),
    );
    return legacy
      ? decodeNamedCharacterReference(legacy) + name.slice(legacy.length)
      : reference;
  });
}

// react-markdown 4, which the queue used before, decoded character references
// without their semicolon, as browsers do (`&nbsp`, `&copy`, `&#160`), and
// course staff wrote messages that way. CommonMark leaves them as text, so this
// decodes them in the parsed text: not in code, or in links' addresses, or in
// a bare address's text, which is its address.
function remarkUnterminatedReferences() {
  const decodeIn = (node, parent) => {
    if (
      node.type === "text" &&
      !(parent.type === "link" && parent.url.endsWith(node.value))
    ) {
      node.value = decodeUnterminated(node.value);
    }
    if (node.title) {
      node.title = decodeUnterminated(node.title);
    }
    for (const child of node.children || []) {
      decodeIn(child, node);
    }
  };
  return (tree) => decodeIn(tree, tree);
}

// Markdown that course staff write in the settings, GitHub-flavored as it was
// with react-markdown 4.
export function Markdown({ children }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm, remarkUnterminatedReferences]}>
      {children}
    </ReactMarkdown>
  );
}
