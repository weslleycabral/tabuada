"""Modo web: servidor local (só 127.0.0.1) com a mesma interface do terminal."""

import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import report, storage
from .drill import Config, Drill, now, parse_answer, parse_tabelas

WEB = Path(__file__).parent / "web"
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/fonts/JetBrainsMono-Regular.woff2": ("fonts/JetBrainsMono-Regular.woff2", "font/woff2"),
    "/fonts/JetBrainsMono-SemiBold.woff2": ("fonts/JetBrainsMono-SemiBold.woff2", "font/woff2"),
}


class Training:
    """Sessão web em andamento (uma por vez)."""

    def __init__(self, config):
        self.history = storage.load_history()
        self.drill = Drill(config, self.history)
        self.started = now()
        self.t_start = time.monotonic()
        self.question = None
        self.asked_at = None
        self.next()

    def next(self):
        self.question = self.drill.next_question()
        self.asked_at = time.monotonic()

    def elapsed(self):
        return time.monotonic() - self.t_start

    def state(self):
        d = self.drill
        return {
            "question": list(self.question),
            "asked": len(d.answers) + 1,
            "n": d.config.n,
            "tempo": d.config.tempo,
            "elapsed": self.elapsed(),
            "ok": sum(1 for a in d.answers if a["ok"]),
            "errors": sum(1 for a in d.answers if not a["ok"] and not a["skipped"]),
            "skipped": sum(1 for a in d.answers if a["skipped"]),
        }

    def finish(self, interrupted):
        if not self.drill.answers:
            return None
        session = self.drill.to_session(self.started, self.elapsed() * 1000, interrupted)
        storage.add_session(session)
        return report.build(session, self.history)


class App:
    def __init__(self):
        self.lock = threading.Lock()
        self.training = None

    # cada método devolve um dicionário JSON

    def home(self, q):
        cfg = storage.load_config()
        sessions = storage.load_history()
        last = Config.from_dict(cfg["last"])
        rows = report.history_rows(sessions)
        return {"config": last.to_dict(), "config_desc": last.describe(),
                "show_shortcuts": cfg["show_shortcuts"], "last": rows[0] if rows else None}

    def history(self, q):
        sessions = storage.load_history()
        streak, _ = report.day_streaks(sessions)
        return {"rows": report.history_rows(sessions), "streak": streak}

    def report(self, q):
        sid = q.get("id")
        rep = report.build_for_id(storage.load_history(), int(sid) if sid else None)
        return {"report": rep}

    def stats(self, q):
        return report.stats(storage.load_history(), q.get("modo", "dominio"))

    def weak(self, q):
        return report.weak_facts(storage.load_history(), int(q.get("n", 10)))

    def preview(self, body):
        cfg = self._config(body)
        return {"desc": cfg.describe(), "command": cfg.command()}

    def shortcuts(self, body):
        storage.update_config(show_shortcuts=bool(body.get("show")))
        return {"ok": True}

    def start(self, body):
        cfg = self._config(body) if body.get("config") else \
            Config.from_dict(storage.load_config()["last"])
        storage.update_config(last=cfg.to_dict())
        self.training = Training(cfg)
        return {"desc": cfg.describe(), "state": self.training.state()}

    def answer(self, body):
        tr = self.training
        if tr is None:
            raise ValueError("Nenhum treino em andamento.")
        kind, value = parse_answer(str(body.get("input", "")))
        if kind == "invalid":
            return {"invalid": True}
        if kind == "quit":
            return self._end(True, None)
        ms = (time.monotonic() - tr.asked_at) * 1000
        a, b = tr.question
        ans = tr.drill.record(a, b, value, ms, skipped=(kind == "skip"))
        feedback = dict(ans, right=a * b, slow=ans["ok"] and tr.drill.is_slow(ans["ms"]))
        if tr.drill.done(tr.elapsed()):
            return self._end(False, feedback)
        tr.next()
        return {"feedback": feedback, "state": tr.state()}

    def quit(self, body):
        return self._end(True, None)

    def _end(self, interrupted, feedback):
        tr, self.training = self.training, None
        rep = tr.finish(interrupted) if tr else None
        return {"feedback": feedback, "done": True, "report": rep}

    @staticmethod
    def _config(body):
        c = body.get("config") or {}
        tabelas = parse_tabelas(c.get("tabelas", "todas")) if isinstance(c.get("tabelas", "todas"), str) \
            else c["tabelas"]
        tempo = int(c["tempo"]) if c.get("tempo") else None
        n = None if tempo else int(c.get("n") or 20)
        return Config(tabelas=tabelas, n=n, tempo=tempo, foco=bool(c.get("foco")))


GET_ROUTES = {"/api/home": "home", "/api/history": "history", "/api/report": "report",
              "/api/stats": "stats", "/api/weak": "weak"}
POST_ROUTES = {"/api/preview": "preview", "/api/shortcuts": "shortcuts", "/api/start": "start",
               "/api/answer": "answer", "/api/quit": "quit"}


def make_handler(app, allowed_hosts):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code, data):
            self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"))

        def _host_ok(self):
            # evita que outros sites leiam o servidor via DNS rebinding
            return self.headers.get("Host") in allowed_hosts

        def do_GET(self):
            if not self._host_ok():
                return self._send(403, b"forbidden", "text/plain")
            url = urlparse(self.path)
            if url.path in STATIC:
                name, ctype = STATIC[url.path]
                return self._send(200, (WEB / name).read_bytes(), ctype)
            if url.path in GET_ROUTES:
                q = {k: v[0] for k, v in parse_qs(url.query).items()}
                return self._call(GET_ROUTES[url.path], q)
            self._send(404, b"not found", "text/plain")

        def do_POST(self):
            if not self._host_ok() or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self._send(403, b"forbidden", "text/plain")
            url = urlparse(self.path)
            if url.path not in POST_ROUTES:
                return self._send(404, b"not found", "text/plain")
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self._json(400, {"error": "JSON inválido."})
            self._call(POST_ROUTES[url.path], body)

        def _call(self, name, arg):
            try:
                with app.lock:
                    data = getattr(app, name)(arg)
            except ValueError as e:
                return self._json(400, {"error": str(e)})
            self._json(200, data)

    return Handler


def run(port=0, open_browser=True):
    app = App()
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app, set()))
    real_port = server.server_address[1]
    server.RequestHandlerClass = make_handler(
        app, {"127.0.0.1:%d" % real_port, "localhost:%d" % real_port})
    url = "http://127.0.0.1:%d/" % real_port
    print("\n  Tabuada no navegador: %s" % url)
    print("  Ctrl+C aqui encerra.\n")
    if open_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Até a próxima!\n")
    finally:
        server.server_close()
    return 0
