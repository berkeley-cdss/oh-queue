"""The tags that add the React app (src/, built by Vite) to the course page.

`yarn build` writes the bundle to oh_queue/static/dist, with a manifest of its hashed
file names, and the page links to them. In development, with VITE_DEV_SERVER set (to
`yarn dev`'s address, such as http://localhost:5173), the page loads the app from Vite's
dev server instead, so changes show up without rebuilding.
"""

import json
import os

from flask import current_app, url_for
from markupsafe import Markup, escape

ENTRY = "src/main.jsx"
DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "dist")
MANIFEST = os.path.join(DIST, ".vite", "manifest.json")

# From Vite's backend integration guide, for @vitejs/plugin-react's fast refresh.
REFRESH_PREAMBLE = """<script type="module">
  import RefreshRuntime from "{server}/static/dist/@react-refresh";
  RefreshRuntime.injectIntoGlobalHook(window);
  window.$RefreshReg$ = () => {{}};
  window.$RefreshSig$ = () => (type) => type;
  window.__vite_plugin_react_preamble_installed__ = true;
</script>"""

_manifest = None


def _read_manifest():
    """The build's manifest, or None if there's no build. Read once in production, and
    on every page in development, where the build can change while the server runs."""
    global _manifest
    if _manifest is None or current_app.config["ENV"] == "dev":
        try:
            with open(MANIFEST) as f:
                _manifest = json.load(f)
        except FileNotFoundError:
            if current_app.config["ENV"] != "dev":
                raise RuntimeError("The frontend isn't built: run `yarn build`.")
            return None
    return _manifest


def vite_tags():
    server = os.environ.get("VITE_DEV_SERVER", "").rstrip("/")
    if server and current_app.config["ENV"] == "dev":
        server = escape(server)
        return Markup(
            REFRESH_PREAMBLE.format(server=server)
            + f'\n<script type="module" src="{server}/static/dist/@vite/client"></script>'
            + f'\n<script type="module" src="{server}/static/dist/{ENTRY}"></script>'
        )

    manifest = _read_manifest()
    if manifest is None:
        # The tests render the page without Node, so without a build.
        return Markup("<!-- The frontend isn't built: run `yarn build`, or `yarn dev` with VITE_DEV_SERVER set. -->")

    entry = manifest[ENTRY]
    tags = [
        f'<link rel="stylesheet" href="{url_for("static", filename="dist/" + css)}" />'
        for css in entry.get("css", [])
    ]
    tags.append(f'<script type="module" src="{url_for("static", filename="dist/" + entry["file"])}"></script>')
    return Markup("\n".join(tags))
