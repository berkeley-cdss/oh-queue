let LlmTips = ({ tips, className }) => {
  if (!tips) {
    return null;
  }
  const tipClass = classNames("ticket-llm-tips", className);
  return (
    <div className={tipClass}>
      <span className="ticket-llm-tips-title">LLM Tips</span>
      <ReactMarkdown className="ticket-llm-tips-body" source={tips} />
    </div>
  );
};
