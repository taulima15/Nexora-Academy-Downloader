import gc
import ipaddress
import os
import queue
import socket
import shutil
import threading
import time
import uuid

from flask import Flask, Response, jsonify, render_template, request, send_file
from urllib.parse import urlparse

from grabber import SiteGrabber, get_site_name, zip_directory

app = Flask(__name__)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Session TTLs (seconds)
COMPLETE_TTL = 1800
ERROR_TTL = 600
ZOMBIE_TTL = 1800
ORPHAN_TTL = 1800
JANITOR_INTERVAL = 300

# Per-session state
_sessions: dict[str, dict] = {}
_queues: dict[str, queue.Queue] = {}
_cancel_events: dict[str, threading.Event] = {}
_lock = threading.Lock()


# ──────────────────────────────────────────────────────────────────────────────
# Session management
# ──────────────────────────────────────────────────────────────────────────────


def _purge(session_id: str) -> None:
    with _lock:
        result = _sessions.pop(session_id, None)
        _queues.pop(session_id, None)
        _cancel_events.pop(session_id, None)
    if not result:
        return
    for path in (result.get("zip_path"), os.path.join(DOWNLOAD_FOLDER, session_id)):
        if path and os.path.exists(path):
            try:
                if os.path.isfile(path):
                    os.remove(path)
                else:
                    shutil.rmtree(path, ignore_errors=True)
            except Exception:
                pass


def _janitor() -> None:
    while True:
        time.sleep(JANITOR_INTERVAL)
        try:
            now = time.time()
            to_remove = []

            with _lock:
                snapshot = list(_sessions.items())

            for sid, s in snapshot:
                age = now - (s.get("created_at") or s.get("started_at") or 0)
                status = s.get("status")
                if status == "complete" and age > COMPLETE_TTL:
                    to_remove.append(sid)
                elif status == "error" and age > ERROR_TTL:
                    to_remove.append(sid)
                elif status == "processing" and age > ZOMBIE_TTL:
                    to_remove.append(sid)

            for sid in to_remove:
                _purge(sid)

            # Orphan files
            with _lock:
                known = set(_sessions.keys())
            for entry in os.listdir(DOWNLOAD_FOLDER):
                path = os.path.join(DOWNLOAD_FOLDER, entry)
                base = entry[:-4] if entry.endswith(".zip") else entry
                if base in known:
                    continue
                try:
                    age = now - os.path.getmtime(path)
                except OSError:
                    continue
                if age > ORPHAN_TTL:
                    try:
                        if os.path.isfile(path):
                            os.remove(path)
                        else:
                            shutil.rmtree(path, ignore_errors=True)
                    except Exception:
                        pass

            gc.collect()
        except Exception:
            pass


threading.Thread(target=_janitor, daemon=True).start()


# ──────────────────────────────────────────────────────────────────────────────
# Download worker
# ──────────────────────────────────────────────────────────────────────────────


def _worker(session_id: str, url: str) -> None:
    with _lock:
        q = _queues.get(session_id)
        cancel_event = _cancel_events.get(session_id)
    if q is None or cancel_event is None:
        return

    dl_dir = os.path.join(DOWNLOAD_FOLDER, session_id)
    zip_path = os.path.join(DOWNLOAD_FOLDER, f"{session_id}.zip")
    grabber = None

    try:
        grabber = SiteGrabber(url, dl_dir, log=lambda m: q.put(m), cancel_event=cancel_event)
        ok = grabber.grab()

        if cancel_event.is_set():
            q.put("⏹️ Captura cancelada pelo usuário")
            with _lock:
                _sessions[session_id] = {"status": "canceled", "created_at": time.time()}
            return

        if not ok:
            raise RuntimeError("grab() returned False")

        site_name = get_site_name(url)
        q.put("📦 Criando arquivo ZIP...")
        zip_directory(dl_dir, zip_path)

        if os.path.isdir(dl_dir):
            shutil.rmtree(dl_dir, ignore_errors=True)

        q.put("🎉 Download pronto!")
        with _lock:
            _sessions[session_id] = {
                "status": "complete",
                "zip_path": zip_path,
                "filename": f"{site_name}.zip",
                "created_at": time.time(),
            }

    except Exception as exc:
        if cancel_event.is_set():
            q.put("⏹️ Captura cancelada pelo usuário")
            with _lock:
                _sessions[session_id] = {"status": "canceled", "created_at": time.time()}
        else:
            q.put(f"❌ Erro: {exc}")
            with _lock:
                _sessions[session_id] = {
                    "status": "error",
                    "error": str(exc),
                    "created_at": time.time(),
                }
        if os.path.isdir(dl_dir):
            shutil.rmtree(dl_dir, ignore_errors=True)
        if os.path.isfile(zip_path):
            try:
                os.remove(zip_path)
            except Exception:
                pass
    finally:
        grabber = None
        gc.collect()


# ──────────────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    with _lock:
        info = {"status": "ok", "sessions": len(_sessions), "active": sum(1 for s in _sessions.values() if s.get("status") == "processing")}
    return jsonify(info)


@app.route("/start-download", methods=["POST"])
def start_download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "URL é obrigatória"}), 400

    # Auto-prefix scheme so users can paste "example.com" or "//example.com"
    if not url.startswith(("http://", "https://")):
        url = "https://" + url.lstrip("/")

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or not hostname:
        return jsonify({"error": "Informe uma URL HTTP ou HTTPS válida."}), 400
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".local"):
        return jsonify({"error": "Endereços locais não são permitidos."}), 400
    try:
        addresses = {socket.gethostbyname(hostname)}
        if any(ipaddress.ip_address(ip).is_private or ipaddress.ip_address(ip).is_loopback or ipaddress.ip_address(ip).is_link_local for ip in addresses):
            return jsonify({"error": "Endereços de rede interna não são permitidos."}), 400
    except socket.gaierror:
        return jsonify({"error": "Não foi possível resolver o domínio informado."}), 400

    sid = str(uuid.uuid4())
    with _lock:
        _queues[sid] = queue.Queue()
        _cancel_events[sid] = threading.Event()
        _sessions[sid] = {"status": "processing", "started_at": time.time(), "url": url}

    threading.Thread(target=_worker, args=(sid, url), daemon=True).start()
    return jsonify({"session_id": sid})


@app.route("/stream/<session_id>")
def stream(session_id: str):
    def generate():
        with _lock:
            q = _queues.get(session_id)
        if q is None:
            yield "data: ❌ Sessão não encontrada\n\n"
            yield "event: done\ndata: error\n\n"
            return

        deadline = time.time() + 35 * 60  # 35-minute hard cap

        while True:
            if time.time() > deadline:
                yield "data: ⏱️  Tempo esgotado\n\n"
                yield "event: done\ndata: timeout\n\n"
                return
            try:
                msg = q.get(timeout=30)
                yield f"data: {msg}\n\n"
                with _lock:
                    s = _sessions.get(session_id, {})
                if s.get("status") in ("complete", "error", "canceled"):
                    yield f"event: done\ndata: {s['status']}\n\n"
                    return
            except queue.Empty:
                with _lock:
                    s = _sessions.get(session_id, {})
                if s.get("status") in ("complete", "error", "canceled"):
                    yield f"event: done\ndata: {s['status']}\n\n"
                    return
                yield ": keepalive\n\n"

    return Response(generate(), mimetype="text/event-stream")


@app.route("/cancel/<session_id>", methods=["POST"])
def cancel_download(session_id: str):
    with _lock:
        session = _sessions.get(session_id)
        event = _cancel_events.get(session_id)
    if not session or not event:
        return jsonify({"error": "Sessão não encontrada"}), 404
    if session.get("status") != "processing":
        return jsonify({"error": "A captura já terminou"}), 409
    event.set()
    return jsonify({"status": "canceling"})


@app.route("/download-file/<session_id>")
def download_file(session_id: str):
    with _lock:
        s = _sessions.get(session_id)

    if not s or s.get("status") != "complete":
        return "Arquivo não disponível", 404

    zip_path = s.get("zip_path")
    filename = s.get("filename")

    if not zip_path or not os.path.exists(zip_path):
        _purge(session_id)
        return "Arquivo não encontrado", 404

    try:
        resp = send_file(zip_path, as_attachment=True, download_name=filename)

        def cleanup():
            time.sleep(3)
            _purge(session_id)

        threading.Thread(target=cleanup, daemon=True).start()
        return resp
    except Exception as exc:
        return f"Erro ao enviar arquivo: {exc}", 500


if __name__ == "__main__":
    # In production (Railway/Render) gunicorn drives the app via entrypoint.sh.
    # This block only runs for `python app.py` during local dev.
    app.run(host="0.0.0.0", debug=False, port=int(os.environ.get("PORT", 5001)), threaded=True)
