import { Link, useSearchParams } from "react-router-dom";
import { Navbar } from "./navbar";

export function ErrorView({ state, message }) {
  const [searchParams] = useSearchParams();
  const text = message || searchParams.get("message") || "Unknown error";

  return (
    <div>
      <Navbar state={state} mode="error" />
      <div className="container error-view">
        <div className="row">
          <div className="col-xs-12">
            <div className="alert alert-danger">
              <p>{text}</p>
            </div>
            <Link className="btn btn-primary" to="/">
              Home
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
