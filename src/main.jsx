import "bootstrap/dist/css/bootstrap.min.css";
// The pages outside a course' stylesheet, with UC Berkeley's colors and the site
// header, so the course pages look like them, and like sections and seating.
import "../oh_queue/static/pages/css/style.css";
import { createRoot } from "react-dom/client";
import { App } from "./components/app";
import "./style.css";

createRoot(document.getElementById("content")).render(<App />);
