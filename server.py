# server.py — نسخة مبسّطة من السيرفر لتشغيلها جوا تطبيق أندرويد (جهاز واحد، بدون Termux)

import os
import time
import threading
import queue
import json
import uuid
from urllib.parse import unquote, quote

from flask import Flask, request, jsonify, send_file, Response, stream_with_context
from flask_cors import CORS

from mobile_downloader import MediaDownloader

APP_NAME = "SnapYTube Ultimate"
APP_VERSION = "4.1.0"

_rate_lock = threading.Lock()
_rate_hits = []
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 12


def is_rate_limited():
    now = time.time()
    with _rate_lock:
        _rate_hits[:] = [t for t in _rate_hits if now - t < RATE_LIMIT_WINDOW]
        if len(_rate_hits) >= RATE_LIMIT_MAX:
            return True
        _rate_hits.append(now)
        return False


def build_app(storage_path):
    """يبني تطبيق Flask ويربطه بمجلد تخزين التطبيق على أندرويد"""
    download_folder = os.path.join(storage_path, "downloads")
    ffmpeg_path = os.path.join(storage_path, "bin", "ffmpeg")  # شوف README لتفاصيل ffmpeg
    os.makedirs(download_folder, exist_ok=True)

    downloader = MediaDownloader(
        download_folder=download_folder,
        ffmpeg_location=ffmpeg_path if os.path.exists(ffmpeg_path) else None
    )

    app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), "static"))
    CORS(app)

    index_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

    @app.route("/")
    def index():
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "app": APP_NAME, "version": APP_VERSION,
                         "download_folder": download_folder})

    @app.route("/api/check-update")
    def check_update():
        # التطبيق مستقل بالكامل (بدون Termux)، فالتحديث بيصير عن طريق نسخة جديدة من الـ APK
        # مو تحديث حي لـ yt-dlp. منرجع حالة ثابتة هون.
        return jsonify({"status": "success", "checking": False, "updated": False,
                         "version": None, "message": "التحديثات عن طريق نسخة جديدة من التطبيق"})

    @app.route("/api/download", methods=["POST"])
    def api_download():
        if is_rate_limited():
            return jsonify({"status": "error", "message": "⏳ طلبات كتيرة، جرب بعد شوي"}), 429
        data = request.get_json(silent=True) or {}
        url = data.get("url", "").strip()
        if not url:
            return jsonify({"status": "error", "message": "⚠️ الرابط غير صالح"}), 400
        result = downloader.download(url)
        if result["success"]:
            return jsonify({
                "status": "success", "message": "✅ تم تحميل الفيديو بنجاح!",
                "filename": result["filename"], "title": result["title"],
                "platform": result["platform"], "duration": result["duration"],
                "filesize": result["filesize"], "filesize_mb": result["filesize_mb"],
                "quality": result.get("quality"), "thumbnail": result.get("thumbnail"),
                "download_url": f"/api/video/{quote(result['filename'], safe='')}"
            })
        return jsonify({"status": "error", "message": result["error"]}), 500

    @app.route("/api/download/progress", methods=["POST"])
    def api_download_progress():
        if is_rate_limited():
            return jsonify({"status": "error", "message": "⏳ طلبات كتيرة، جرب بعد شوي"}), 429
        data = request.get_json(silent=True) or {}
        url = data.get("url", "").strip()
        if not url:
            return jsonify({"status": "error", "message": "⚠️ الرابط غير صالح"}), 400

        download_id = str(uuid.uuid4())[:8]
        progress_queue = queue.Queue()

        def progress_callback(p):
            try:
                progress_queue.put({"type": "progress", "download_id": download_id, "data": p})
            except Exception:
                pass

        def generate():
            def do_download():
                try:
                    result = downloader.download(url, progress_callback, download_id)
                    if result.get("success"):
                        result["download_url"] = f"/api/video/{quote(result['filename'], safe='')}"
                    progress_queue.put({"type": "complete", "data": result})
                except Exception as e:
                    progress_queue.put({"type": "complete", "data": {"success": False, "error": str(e)}})

            threading.Thread(target=do_download, daemon=True).start()
            while True:
                try:
                    msg = progress_queue.get(timeout=30)
                    yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                    if msg.get("type") == "complete":
                        break
                except queue.Empty:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

        return Response(stream_with_context(generate()), mimetype="text/event-stream",
                         headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    MEDIA_EXTS = {
        "video": (".mp4", ".webm", ".mkv", ".mov"),
        "audio": (".m4a", ".mp3", ".opus", ".aac"),
        "image": (".jpg", ".jpeg", ".png", ".webp"),
    }

    @app.route("/api/files")
    def api_files():
        result = {"video": [], "audio": [], "image": []}
        if os.path.exists(download_folder):
            for f in os.listdir(download_folder):
                low = f.lower()
                kind = next((k for k, exts in MEDIA_EXTS.items() if low.endswith(exts)), None)
                if not kind:
                    continue
                fp = os.path.join(download_folder, f)
                result[kind].append({
                    "name": f, "url": f"/api/video/{quote(f, safe='')}",
                    "size_mb": round(os.path.getsize(fp) / (1024 * 1024), 2),
                    "created": os.path.getctime(fp)
                })
        for k in result:
            result[k].sort(key=lambda x: x["created"], reverse=True)
        return jsonify({"status": "success", "folder": download_folder, "files": result,
                         "count": sum(len(v) for v in result.values())})

    @app.route("/api/videos")
    def api_videos():
        files = []
        if os.path.exists(download_folder):
            for f in os.listdir(download_folder):
                if f.lower().endswith((".mp4", ".webm", ".mkv")):
                    fp = os.path.join(download_folder, f)
                    files.append({"name": f, "url": f"/api/video/{quote(f, safe='')}",
                                  "size_mb": round(os.path.getsize(fp) / (1024 * 1024), 1),
                                  "created": os.path.getctime(fp)})
        files.sort(key=lambda x: x["created"], reverse=True)
        return jsonify({"status": "success", "videos": files, "count": len(files)})

    @app.route("/api/stats")
    def api_stats():
        total_size, count = 0, 0
        if os.path.exists(download_folder):
            for f in os.listdir(download_folder):
                if f.lower().endswith((".mp4", ".webm", ".mkv")):
                    total_size += os.path.getsize(os.path.join(download_folder, f))
                    count += 1
        return jsonify({"status": "success", "total": count,
                         "total_size_mb": round(total_size / (1024 * 1024), 1),
                         "today": 0, "download_folder": download_folder})

    @app.route("/api/video/<path:filename>")
    def api_video(filename):
        filename = os.path.basename(unquote(filename))
        safe_folder = os.path.realpath(download_folder)
        direct_path = os.path.realpath(os.path.join(download_folder, filename))
        if not direct_path.startswith(safe_folder + os.sep) or not os.path.exists(direct_path):
            return jsonify({"error": "الملف غير موجود"}), 404
        return send_file(direct_path, as_attachment=True, download_name=filename)

    return app
