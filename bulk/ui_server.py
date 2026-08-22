"""Bulk Publisher UI — local web dashboard.

  python -m bulk.ui_server            (port 8700; use the SD venv python)

Endpoints:
  GET  /                   dashboard UI
  GET  /api/health         environment audit (LLM / SD / TTS / ffmpeg / secrets)
  GET  /api/state          state ledger summary + books
  GET  /api/candidates?n=  Gutendex top candidates
  POST /api/run            start a batch  {classics, generated, curated[],
                            options{...}}
  GET  /api/logs?after=N   incremental run log
  POST /api/stop           stop the current run (after the current book)
"""
import contextlib
import io
import json
import os
import sys
import threading
import time
import uuid

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

from flask import Flask, jsonify, request, send_from_directory

from bulk.bulk_config import load_bulk_config, resolve_publish

app = Flask(__name__, static_folder=None)
UI_DIR = os.path.join(_HERE, "ui")


# ---------------------------------------------------------------- run manager

class _Tee(io.StringIO):
    """A stream that splits writes into log lines and echoes to real stdout."""

    def __init__(self, log, lock, target):
        super().__init__()
        self._log = log
        self._lock = lock
        self._target = target
        self._buf = ""

    def write(self, s):
        if not s:
            return len(s)
        with self._lock:
            self._buf += s
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                self._log.append(line.rstrip("\r"))
        try:
            self._target.write(s)
            self._target.flush()
        except Exception:
            pass
        return len(s)

    def flush(self):
        with self._lock:
            if self._buf:
                self._log.append(self._buf.rstrip("\r"))
                self._buf = ""
        try:
            self._target.flush()
        except Exception:
            pass


class RunManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._log = []
        self._thread = None
        self._stop = threading.Event()
        self._run_id = None
        self._started_at = None
        self._finished = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def status(self):
        with self._lock:
            return {
                "run_id": self._run_id,
                "running": self.running,
                "started_at": self._started_at,
                "finished": self._finished,
                "lines": len(self._log),
                "last_line": self._log[-1] if self._log else "",
            }

    def start(self, payload):
        if self.running:
            return None, "A run is already in progress — stop it or wait."
        self._log.clear()
        self._stop.clear()
        self._run_id = uuid.uuid4().hex[:8]
        self._started_at = time.strftime("%H:%M:%S")
        self._finished = None
        self._thread = threading.Thread(target=self._worker, args=(payload,),
                                        daemon=True)
        self._thread.start()
        return self._run_id, None

    def stop(self):
        self._stop.set()
        return True

    def _worker(self, payload):
        cfg = load_bulk_config()
        opts = payload.get("options", {}) or {}
        opts.setdefault("dry_run", payload.get("dry_run", False))
        opts.setdefault("no_publish", payload.get("no_publish", False))

        # publish availability drives no_publish fallback inside the pipelines
        log, lock = self._log, self._lock
        try:
            with contextlib.redirect_stdout(_Tee(log, lock, sys.__stdout__)), \
                 contextlib.redirect_stderr(_Tee(log, lock, sys.__stderr__)):
                print("=" * 60)
                print(f"  RUN {self._run_id} started  ({time.strftime('%H:%M:%S')})")
                print("=" * 60)
                pub_ok = bool(resolve_publish(cfg).get("supabase_url"))
                print(f"  publish: {'ENABLED' if pub_ok and not opts['no_publish'] else 'OFF (no-publish)'}")
                if payload.get("action") == "backfill":
                    from bulk.pipeline_classics import backfill_covers
                    print(f"\n>>> BACKFILL AI covers: {payload.get('classics') or 'all'} book(s)")
                    backfill_covers(cfg, opts, stop_event=self._stop,
                                    limit=payload.get("limit", 0))
                elif payload.get("action") == "publish_ready":
                    from bulk.pipeline_classics import publish_ready
                    print("\n>>> PUBLISH READY books (produced locally, not yet on site)")
                    publish_ready(cfg, opts, stop_event=self._stop,
                                  limit=payload.get("limit", 0))
                elif payload.get("classics"):
                    from bulk.pipeline_classics import run_classics
                    curated = payload.get("curated") or None
                    print(f"\n>>> CLASSICS batch: {payload['classics']} book(s)")
                    run_classics(cfg, int(payload["classics"]), curated, opts,
                                 stop_event=self._stop)
                if payload.get("generated"):
                    from bulk.pipeline_generated import run_generated
                    print(f"\n>>> GENERATED batch: {payload['generated']} book(s)")
                    run_generated(cfg, int(payload["generated"]), opts,
                                  stop_event=self._stop)
                print("\n" + "=" * 60)
                print(f"  RUN finished  ({time.strftime('%H:%M:%S')})")
                print("=" * 60)
        except Exception as e:
            import traceback
            print(f"[UI ERROR] {e}")
            traceback.print_exc()
        finally:
            self._finished = time.strftime("%H:%M:%S")


RUNNER = RunManager()


# ---------------------------------------------------------------- routes

@app.get("/")
def index():
    return send_from_directory(UI_DIR, "index.html")


@app.get("/api/health")
def api_health():
    from bulk.envcheck import full_check
    refresh = request.args.get("refresh", "") == "1"
    return jsonify(full_check(load_bulk_config(), refresh=refresh))


@app.get("/api/state")
def api_state():
    from bulk.state import BulkState
    cfg = load_bulk_config()
    state = BulkState(cfg["bulk"]["state_file"])
    books = state.all()
    summary = {
        "total": len(books),
        "published": sum(1 for b in books if b.get("status") == "published"),
        "ready": sum(1 for b in books if b.get("status") == "ready"),
        "failed": sum(1 for b in books if b.get("status") == "failed"),
        "skipped": sum(1 for b in books if b.get("status") == "skipped"),
        "planned": sum(1 for b in books if b.get("status") == "planned"),
    }
    return jsonify({"summary": summary, "books": books,
                    "run": RUNNER.status()})


@app.get("/api/candidates")
def api_candidates():
    n = min(int(request.args.get("n", 25)), 50)
    from bulk.gutendex import top_books, author_name
    from bulk.pipeline_classics import _title_clean
    cfg = load_bulk_config()
    b = cfg["bulk"]
    books = top_books(n, lang=b.get("language", "en"),
                      min_downloads=b.get("min_downloads", 0))
    out = []
    for bk in books:
        out.append({
            "id": bk["id"],
            "title": _title_clean(bk.get("title", "")),
            "author": author_name(bk),
            "downloads": bk.get("download_count", 0),
        })
    return jsonify(out)


@app.post("/api/run")
def api_run():
    payload = request.get_json(force=True, silent=True) or {}
    run_id, err = RUNNER.start(payload)
    if err:
        return jsonify({"error": err}), 409
    return jsonify({"ok": True, "run_id": run_id})


@app.get("/api/logs")
def api_logs():
    after = int(request.args.get("after", 0))
    with RUNNER._lock:
        lines = RUNNER._log[after:]
    return jsonify({"after": after + len(lines), "lines": lines,
                    "running": RUNNER.running})


@app.post("/api/stop")
def api_stop():
    RUNNER.stop()
    return jsonify({"ok": True})


def main(port=8700, host="127.0.0.1"):
    print("=" * 60)
    print("  Bulk Publisher UI  ->  http://127.0.0.1:%d" % port)
    print("  (close this window to stop the server)")
    print("=" * 60)
    app.run(host=host, port=port, threaded=True)


if __name__ == "__main__":
    port = int(os.environ.get("BULK_UI_PORT", "8700"))
    main(port=port)
