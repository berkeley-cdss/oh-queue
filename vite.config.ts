import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Flask renders the course page (oh_queue/templates/index.html), so the course name and
// the offering's path are in it, and adds this bundle to it (oh_queue/vite.py). In
// development the page loads the bundle from Vite's dev server instead, which runs on
// :5173 alongside `python manage.py run_server`.
export default defineConfig({
  plugins: [react()],
  // where Flask serves the build from
  base: "/static/dist/",
  build: {
    outDir: "oh_queue/static/dist",
    emptyOutDir: true,
    // oh_queue/vite.py reads it to find the bundle's hashed file names
    manifest: true,
    // The whole app is one bundle, like the scripts it replaced; it isn't split up yet.
    chunkSizeWarningLimit: 1000,
    rolldownOptions: {
      input: "src/main.jsx",
    },
  },
  server: {
    port: 5173,
    strictPort: true,
  },
});
