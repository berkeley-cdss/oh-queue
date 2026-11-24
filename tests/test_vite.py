"""The tags that add the React app to the course page (oh_queue/vite.py)."""

import json

import pytest

from oh_queue import vite


@pytest.fixture()
def manifest(tmp_path, monkeypatch):
    """A build's manifest, as `yarn build` writes it."""
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({
        "src/main.jsx": {"file": "assets/main-abc123.js", "css": ["assets/main-def456.css"], "isEntry": True},
    }))
    monkeypatch.setattr(vite, "MANIFEST", str(path))
    monkeypatch.setattr(vite, "_manifest", None)
    monkeypatch.delenv("VITE_DEV_SERVER", raising=False)
    return path


def test_the_build(app, manifest):
    with app.test_request_context():
        tags = vite.vite_tags()
    assert '<link rel="stylesheet" href="/static/dist/assets/main-def456.css" />' in tags
    assert '<script type="module" src="/static/dist/assets/main-abc123.js"></script>' in tags


def test_the_dev_server_in_development(app, manifest, monkeypatch):
    monkeypatch.setenv("VITE_DEV_SERVER", "http://localhost:5173/")
    with app.test_request_context():
        tags = vite.vite_tags()
    assert 'src="http://localhost:5173/static/dist/@vite/client"' in tags
    assert 'src="http://localhost:5173/static/dist/src/main.jsx"' in tags
    assert 'import RefreshRuntime from "http://localhost:5173/static/dist/@react-refresh"' in tags
    assert "main-abc123.js" not in tags


def test_never_the_dev_server_in_production(app, manifest, monkeypatch):
    monkeypatch.setenv("VITE_DEV_SERVER", "http://localhost:5173")
    monkeypatch.setitem(app.config, "ENV", "prod")
    with app.test_request_context():
        tags = vite.vite_tags()
    assert "localhost:5173" not in tags
    assert "main-abc123.js" in tags


def test_no_build_in_development(app, manifest):
    manifest.unlink()
    with app.test_request_context():
        assert vite.vite_tags().startswith("<!--")


def test_no_build_in_production(app, manifest, monkeypatch):
    manifest.unlink()
    monkeypatch.setitem(app.config, "ENV", "prod")
    with app.test_request_context(), pytest.raises(RuntimeError, match="yarn build"):
        vite.vite_tags()


def test_page_includes_the_tags(client, manifest):
    response = client.get("/offerings/101/")
    assert b"/static/dist/assets/main-abc123.js" in response.data
