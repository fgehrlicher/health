"""The `health` CLI: which requests it sends, and its exit codes.

The CLI is tested against a stub server, so it runs without a database. The
API's own behaviour is covered by the API tests.
"""

import importlib.machinery
import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

CLI_PATH = Path(__file__).resolve().parents[2] / "tools" / "health"


def load_cli():
    loader = importlib.machinery.SourceFileLoader("health_cli", str(CLI_PATH))
    spec = importlib.util.spec_from_loader("health_cli", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


cli = load_cli()


class Stub:
    """Answers each request with the next canned response, and records it."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.seen = []
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def _answer(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else None
                stub.seen.append(
                    (self.command, urlparse(self.path), json.loads(body) if body else None)
                )
                status, payload = stub.responses.pop(0)
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = do_PATCH = do_DELETE = _answer

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def stub():
    servers = []

    def make(*responses):
        server = Stub(responses)
        servers.append(server)
        return server

    yield make
    for server in servers:
        server.close()


def run(url, *args):
    return cli.main(["--url", url, *args])


def test_search_sends_query_and_limit(stub, capsys):
    server = stub((200, {"items": [], "total": 0}))
    assert run(server.url, "foods", "search", "quark", "--limit", "3") == 0
    method, url, _ = server.seen[0]
    assert method == "GET" and url.path == "/api/foods"
    assert parse_qs(url.query) == {"q": ["quark"], "limit": ["3"]}
    assert json.loads(capsys.readouterr().out) == {"items": [], "total": 0}


def test_meal_log_is_a_dry_run_unless_committed(stub, tmp_path, capsys):
    meal = tmp_path / "meal.json"
    meal.write_text(json.dumps({"items": []}), encoding="utf-8")
    server = stub((200, {"id": 1}), (201, {"id": 2}))
    assert run(server.url, "meal", "log", "--file", str(meal)) == 0
    assert parse_qs(server.seen[0][1].query) == {"dry_run": ["true"]}
    assert "nothing was stored" in capsys.readouterr().err
    assert run(server.url, "meal", "log", "--file", str(meal), "--commit") == 0
    assert "dry_run" not in parse_qs(server.seen[1][1].query)


def test_rejected_input_prints_issues_and_exits_2(stub, tmp_path, capsys):
    meal = tmp_path / "meal.json"
    meal.write_text("{}", encoding="utf-8")
    detail = [{"field": "items.0.food", "message": "unknown food 'x'"}]
    server = stub((422, {"detail": detail}))
    assert run(server.url, "meal", "log", "--file", str(meal)) == 2
    printed = json.loads(capsys.readouterr().out)
    assert printed == {"error": "rejected", "issues": detail}


def test_fastapi_validation_errors_are_mapped_to_fields():
    issues = cli.issues_of([{"loc": ["body", "items", 0, "amount"], "msg": "must be positive"}])
    assert issues == [{"field": "items.0.amount", "message": "must be positive"}]


def test_missing_food_exits_3(stub, capsys):
    server = stub((404, {"detail": "Food not found"}))
    assert run(server.url, "foods", "get", "nope") == 3
    assert server.seen[0][1].path == "/api/foods/nope"


def test_day_defaults_to_today_in_berlin(stub, monkeypatch):
    monkeypatch.setattr(cli, "today", lambda: "2026-01-15")
    server = stub((200, {"date": "2026-01-15", "meals": []}))
    assert run(server.url, "day") == 0
    assert server.seen[0][1].path == "/api/log/days/2026-01-15"


def test_unreachable_api_exits_4(capsys):
    assert run("http://127.0.0.1:9", "foods", "search", "x") == 4
    assert json.loads(capsys.readouterr().out)["error"] == "API unreachable"


def test_cook_list_passes_filters(stub):
    server = stub((200, []))
    assert run(server.url, "cook", "list", "--recipe", "chia-pudding", "--since", "2026-01-01") == 0
    query = parse_qs(server.seen[0][1].query)
    assert query["recipe"] == ["chia-pudding"] and query["since"] == ["2026-01-01"]
    assert "until" not in query
