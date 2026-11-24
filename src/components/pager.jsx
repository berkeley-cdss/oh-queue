// Previous and Next buttons for a list shown a page at a time.
export function Pager({ page, setPage, pages }) {
  return (
    <nav aria-label="Pages" className="d-flex justify-content-between my-3">
      <button
        type="button"
        className="btn btn-outline-secondary"
        onClick={() => setPage((page) => page - 1)}
        disabled={page <= 0}
      >
        Previous
      </button>
      <button
        type="button"
        className="btn btn-outline-secondary"
        onClick={() => setPage((page) => page + 1)}
        disabled={page >= pages - 1}
      >
        Next
      </button>
    </nav>
  );
}
