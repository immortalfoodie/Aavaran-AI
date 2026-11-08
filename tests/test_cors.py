"""CORS must survive common copy-paste mistakes in CORS_ORIGINS (trailing slash, quotes, spaces)."""

import importlib

from fastapi.testclient import TestClient

SITE = "https://aavaran-ai-final.vercel.app"


def _client(monkeypatch, origins: str, regex: str | None = None) -> TestClient:
    monkeypatch.setenv("CORS_ORIGINS", origins)
    if regex:
        monkeypatch.setenv("CORS_ORIGIN_REGEX", regex)
    else:
        monkeypatch.delenv("CORS_ORIGIN_REGEX", raising=False)
    import api.main as main

    return TestClient(importlib.reload(main).app)


def _preflight(client: TestClient, origin: str):
    return client.options(
        "/api/v1/voice/start",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"},
    )


def test_trailing_slash_and_quotes_are_forgiven(monkeypatch):
    client = _client(monkeypatch, f' "{SITE}/" , http://localhost:5173/ ')
    r = _preflight(client, SITE)
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == SITE


def test_unknown_origin_still_blocked(monkeypatch):
    client = _client(monkeypatch, SITE)
    assert _preflight(client, "https://evil.example").status_code == 400


def test_preview_deployments_via_regex(monkeypatch):
    client = _client(monkeypatch, SITE, r"https://aavaran-ai-.*\.vercel\.app")
    r = _preflight(client, "https://aavaran-ai-git-feature-x.vercel.app")
    assert r.status_code == 200


def teardown_module(module):
    # restore the app with default settings for the rest of the suite
    import os

    os.environ.pop("CORS_ORIGINS", None)
    os.environ.pop("CORS_ORIGIN_REGEX", None)
    import api.main as main

    importlib.reload(main)
