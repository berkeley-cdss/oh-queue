import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Markdown that course staff write in the settings, GitHub-flavored as it was with
// react-markdown 4, which the queue used before.
export function Markdown({ children }) {
  return <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>;
}
