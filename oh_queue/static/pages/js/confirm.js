// Asks before submitting a form with data-confirm="<question>". Copied from sections.
document.addEventListener("submit", (event) => {
  const question = event.target.dataset.confirm;
  if (question && !confirm(question)) {
    event.preventDefault();
  }
});
