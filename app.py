"""
app.py — Flask Application
============================
The main entry point for the Content Automation Demo.
Handles routing, authentication, and SSE streaming.

Teaching notes:
- App factory pattern: create_app() returns a configured Flask app
- SSE (Server-Sent Events): real-time updates without WebSockets
- Session auth: simple username/password, stored in Flask session
"""

import os
import json
import queue
import threading
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, jsonify, Response, flash
)
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from models import (
    init_db, create_content_item, get_content_item, list_content_items,
    update_content_item, delete_content_item, add_pipeline_log,
    get_pipeline_logs, get_setting, set_setting, create_schedule_slot,
    list_schedule_slots, list_content_items_by_statuses, get_calendar_counts
)
from pipeline import run_pipeline, stage_publish, regenerate_image


# ===========================================================================
# APP FACTORY
# ===========================================================================

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # -- Configuration --
    app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
    app.config["ADMIN_USER"] = os.getenv("ADMIN_USER", "admin")
    app.config["ADMIN_PASS"] = os.getenv("ADMIN_PASS", "admin")

    # Initialize the database on startup
    init_db()

    # -- Scheduling background thread --
    # Checks every 60 seconds for scheduled items whose scheduled_at has passed
    def scheduling_loop():
        import time as _time
        while True:
            _time.sleep(60)
            try:
                with app.app_context():
                    scheduled = list_content_items_by_statuses(["scheduled"])
                    now = datetime.now().isoformat()
                    for item in scheduled:
                        if item.get("scheduled_at") and item["scheduled_at"] <= now:
                            try:
                                stage_publish(item["id"], lambda *a, **kw: None)
                            except Exception:
                                update_content_item(item["id"], status="failed")
            except Exception:
                pass

    scheduler_thread = threading.Thread(target=scheduling_loop, daemon=True)
    scheduler_thread.start()

    # -- Store for active SSE streams --
    # Maps content_id -> list of queue.Queue objects (one per connected client)
    active_streams = {}
    streams_lock = threading.Lock()

    # -----------------------------------------------------------------------
    # AUTH: Simple session-based authentication
    # -----------------------------------------------------------------------
    def login_required(f):
        """Decorator: redirect to login if not authenticated."""
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get("logged_in"):
                return redirect(url_for("login_page"))
            return f(*args, **kwargs)
        return decorated

    # -----------------------------------------------------------------------
    # TEMPLATE CONTEXT: Inject common variables into all templates
    # -----------------------------------------------------------------------
    @app.context_processor
    def inject_globals():
        """Make common variables available in all templates."""
        return {
            "current_year": datetime.now().year,
            "app_name": "Content Automation Demo"
        }

    # -----------------------------------------------------------------------
    # AUTH ROUTES
    # -----------------------------------------------------------------------
    @app.route("/login", methods=["GET"])
    def login_page():
        """Show the login form."""
        if session.get("logged_in"):
            return redirect(url_for("dashboard"))
        return render_template("login.html", current_page="login")

    @app.route("/login", methods=["POST"])
    def login():
        """Check credentials and set session."""
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if (username == app.config["ADMIN_USER"] and
                password == app.config["ADMIN_PASS"]):
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials", "error")
            return redirect(url_for("login_page"))

    @app.route("/logout")
    def logout():
        """Clear the session and redirect to login."""
        session.clear()
        return redirect(url_for("login_page"))

    # -----------------------------------------------------------------------
    # PAGE ROUTES (serve HTML templates)
    # -----------------------------------------------------------------------
    @app.route("/")
    @login_required
    def dashboard():
        """Dashboard: content library grid with status badges."""
        items = list_content_items()
        return render_template("dashboard.html", items=items, current_page="dashboard")

    @app.route("/cam")
    @login_required
    def cam():
        """CAM: Content Automation Machine — queue + mini-calendar interface."""
        return render_template("cam.html", current_page="cam")

    @app.route("/content/<int:item_id>")
    @login_required
    def content_detail(item_id):
        """Content detail: single item view with full pipeline log."""
        item = get_content_item(item_id)
        if not item:
            flash("Content item not found", "error")
            return redirect(url_for("dashboard"))
        logs = get_pipeline_logs(item_id)

        # Parse captions JSON into a dict for the template
        captions_parsed = {}
        if item.get("captions"):
            try:
                captions_parsed = json.loads(item["captions"])
            except (json.JSONDecodeError, TypeError):
                captions_parsed = {}

        # Parse stage_durations and stage_costs JSON
        stage_durations = {}
        if item.get("stage_durations"):
            try:
                stage_durations = json.loads(item["stage_durations"])
            except (json.JSONDecodeError, TypeError):
                stage_durations = {}

        stage_costs = {}
        if item.get("stage_costs"):
            try:
                stage_costs = json.loads(item["stage_costs"])
            except (json.JSONDecodeError, TypeError):
                stage_costs = {}

        # Build stage_info list for template
        stages = ["scrape", "script", "image", "video", "caption", "publish"]
        stage_info = []
        for s in stages:
            stage_info.append({
                "name": s,
                "duration": stage_durations.get(s),
                "cost": stage_costs.get(s),
            })

        # Compute completed, error, skipped stages from logs
        completed_stages = set()
        error_stages = set()
        skipped_stages = set()
        for log in logs:
            if log.get("status") == "done":
                completed_stages.add(log.get("stage", ""))
            elif log.get("status") == "error":
                error_stages.add(log.get("stage", ""))
            elif log.get("status") == "skipped":
                skipped_stages.add(log.get("stage", ""))

        return render_template("content_detail.html", item=item, logs=logs,
                               captions_parsed=captions_parsed,
                               stage_info=stage_info,
                               completed_stages=completed_stages,
                               error_stages=error_stages,
                               skipped_stages=skipped_stages,
                               current_page="content")

    @app.route("/settings")
    @login_required
    def settings_page():
        """Settings: API keys + model configuration."""
        settings = {
            "openrouter_api_key": get_setting("openrouter_api_key", ""),
            "firecrawl_api_key": get_setting("firecrawl_api_key", ""),
            "kie_api_key": get_setting("kie_api_key", ""),
            "getlate_api_key": get_setting("getlate_api_key", ""),
            "default_model": get_setting("default_model", "google/gemini-2.5-flash"),
            "default_platform": get_setting("default_platform", "instagram"),
            "headshot_url": get_setting("headshot_url", ""),
            "headshot_enabled": get_setting("headshot_enabled", "false"),
            "r2_account_id": get_setting("r2_account_id", ""),
            "r2_access_key_id": get_setting("r2_access_key_id", ""),
            "r2_secret_access_key": get_setting("r2_secret_access_key", ""),
            "r2_bucket_name": get_setting("r2_bucket_name", ""),
            "r2_public_url": get_setting("r2_public_url", ""),
        }
        return render_template("settings.html", settings=settings,
                               current_page="settings")

    # -----------------------------------------------------------------------
    # API ROUTES
    # -----------------------------------------------------------------------

    @app.route("/api/health")
    def api_health():
        """Health check endpoint."""
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0"
        })

    @app.route("/api/content")
    @login_required
    def api_content_list():
        """JSON list of all content items."""
        items = list_content_items()
        return jsonify(items)

    @app.route("/api/content/<int:item_id>")
    @login_required
    def api_content_detail(item_id):
        """JSON single item + pipeline logs."""
        item = get_content_item(item_id)
        if not item:
            return jsonify({"error": "Not found"}), 404
        logs = get_pipeline_logs(item_id)
        return jsonify({"item": item, "logs": logs})

    @app.route("/api/content/<int:item_id>", methods=["DELETE"])
    @login_required
    def api_content_delete(item_id):
        """Delete a content item."""
        item = get_content_item(item_id)
        if not item:
            return jsonify({"error": "Not found"}), 404
        delete_content_item(item_id)
        return jsonify({"success": True, "message": f"Item {item_id} deleted"})

    @app.route("/api/settings", methods=["POST"])
    @login_required
    def api_settings_save():
        """Save settings (JSON key-value pairs)."""
        data = request.json or {}
        for key, value in data.items():
            set_setting(key, value)

            # Also update environment variables so services pick them up immediately
            env_map = {
                "openrouter_api_key": "OPENROUTER_API_KEY",
                "firecrawl_api_key": "FIRECRAWL_API_KEY",
                "kie_api_key": "KIE_API_KEY",
                "getlate_api_key": "GETLATE_API_KEY",
                "r2_account_id": "R2_ACCOUNT_ID",
                "r2_access_key_id": "R2_ACCESS_KEY_ID",
                "r2_secret_access_key": "R2_SECRET_ACCESS_KEY",
                "r2_bucket_name": "R2_BUCKET_NAME",
                "r2_public_url": "R2_PUBLIC_URL",
            }
            if key in env_map:
                os.environ[env_map[key]] = value

        return jsonify({"success": True, "message": "Settings saved"})

    # -------------------------------------------------------------------
    # HEADSHOT UPLOAD
    # -------------------------------------------------------------------

    @app.route("/api/settings/headshot", methods=["POST"])
    @login_required
    def api_headshot_upload():
        """Upload a headshot image via R2 storage."""
        if "headshot" not in request.files:
            return jsonify({"error": "No file provided"}), 400
        file = request.files["headshot"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400
        try:
            from services.r2_storage import upload_headshot
            file_data = file.read()
            url = upload_headshot(file_data, file.filename)
            set_setting("headshot_url", url)
            return jsonify({"success": True, "url": url})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # -------------------------------------------------------------------
    # CAM API ROUTES
    # -------------------------------------------------------------------

    @app.route("/cam/api/queue")
    @login_required
    def cam_api_queue():
        """Return queue items grouped by processing, completed, failed with progress %."""
        progress_map = {
            "draft": 0, "scraping": 10, "scripting": 25, "scripted": 40,
            "imaging": 50, "imaged": 60, "videoing": 70, "videoed": 80,
            "captioning": 85, "captioned": 90, "uploading": 95,
            "ready": 100, "scheduled": 100, "published": 100, "failed": 0,
        }
        processing_statuses = [
            "draft", "scraping", "scripting", "scripted", "imaging",
            "imaged", "videoing", "videoed", "captioning", "captioned", "uploading"
        ]
        completed_statuses = ["ready", "scheduled", "published"]
        failed_statuses = ["failed"]

        processing = list_content_items_by_statuses(processing_statuses)
        completed = list_content_items_by_statuses(completed_statuses)
        failed = list_content_items_by_statuses(failed_statuses)

        # Add progress percentage to each item
        for item in processing:
            item["progress"] = progress_map.get(item.get("status", ""), 0)
        for item in completed:
            item["progress"] = progress_map.get(item.get("status", ""), 100)
        for item in failed:
            item["progress"] = 0

        return jsonify({
            "processing": processing,
            "completed": completed,
            "failed": failed,
            "totals": {
                "processing": len(processing),
                "completed": len(completed),
                "failed": len(failed),
            }
        })

    @app.route("/cam/api/calendar")
    @login_required
    def cam_api_calendar():
        """Return calendar counts for a given year/month."""
        now = datetime.now()
        year = request.args.get("year", now.year, type=int)
        month = request.args.get("month", now.month, type=int)
        counts = get_calendar_counts(year, month)
        return jsonify(counts)

    @app.route("/cam/api/create", methods=["POST"])
    @login_required
    def cam_api_create():
        """Create content item via CAM — wraps the existing generate endpoint."""
        return api_generate()

    @app.route("/cam/api/approve/<int:item_id>", methods=["POST"])
    @login_required
    def cam_api_approve(item_id):
        """Approve a content item: set status=scheduled + scheduled_at."""
        item = get_content_item(item_id)
        if not item:
            return jsonify({"error": "Not found"}), 404
        data = request.json or {}
        scheduled_at = data.get("scheduled_at") or datetime.now().isoformat()
        update_content_item(item_id, status="scheduled", scheduled_at=scheduled_at)
        return jsonify({"success": True, "scheduled_at": scheduled_at})

    @app.route("/cam/api/retry/<int:item_id>", methods=["POST"])
    @login_required
    def cam_api_retry(item_id):
        """Retry a failed content item by resetting status to draft."""
        item = get_content_item(item_id)
        if not item:
            return jsonify({"error": "Not found"}), 404
        update_content_item(item_id, status="draft")
        return jsonify({"success": True, "message": f"Item {item_id} reset to draft"})

    @app.route("/cam/api/item/<int:item_id>", methods=["DELETE"])
    @login_required
    def cam_api_delete(item_id):
        """Hard delete a content item."""
        item = get_content_item(item_id)
        if not item:
            return jsonify({"error": "Not found"}), 404
        delete_content_item(item_id)
        return jsonify({"success": True, "message": f"Item {item_id} deleted"})

    # -------------------------------------------------------------------
    # SSE STREAMING: The heart of the Automation X-ray
    # -------------------------------------------------------------------

    @app.route("/api/generate", methods=["POST"])
    @login_required
    def api_generate():
        """
        Generate content from a URL or idea.
        Returns an SSE stream that emits events as the pipeline runs.

        The pipeline runs SYNCHRONOUSLY inside the generator function.
        This is intentional for teaching — students see the sequential flow.
        """
        data = request.json or {}
        input_text = data.get("input_text", "").strip()
        platform = data.get("platform", "instagram")
        include_video = data.get("include_video", False)

        if not input_text:
            return jsonify({"error": "input_text is required"}), 400

        # Create the content item
        content_id = create_content_item(input_text, platform=platform,
                                          include_video=include_video)

        # Create a queue for this stream
        event_queue = queue.Queue()
        with streams_lock:
            if content_id not in active_streams:
                active_streams[content_id] = []
            active_streams[content_id].append(event_queue)

        def generate():
            """Generator that runs the pipeline and yields SSE events."""
            def emit_event(stage, status, message, detail=None):
                """
                Emit an SSE event AND log it to the database.
                This is the callback passed to pipeline.py and all services.
                """
                event_data = {
                    "stage": stage,
                    "status": status,
                    "message": message,
                    "detail": detail or {},
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "content_id": content_id
                }
                event_str = json.dumps(event_data)

                # Log to database
                add_pipeline_log(content_id, stage, status, message,
                                json.dumps(detail or {}))

                # Push to all connected clients for this content_id
                with streams_lock:
                    for q in active_streams.get(content_id, []):
                        q.put(event_str)

            # Run the pipeline (this blocks until all stages complete)
            run_pipeline(content_id, emit_event)

            # Signal end of stream
            end_event = json.dumps({
                "stage": "pipeline", "status": "done",
                "message": "Stream complete",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "content_id": content_id
            })
            with streams_lock:
                for q in active_streams.get(content_id, []):
                    q.put(end_event)
                    q.put(None)  # Sentinel to stop the generator

        # Run the pipeline in a background thread
        thread = threading.Thread(target=generate, daemon=True)
        thread.start()

        def stream():
            """Yield SSE events from the queue."""
            try:
                while True:
                    event_str = event_queue.get(timeout=900)  # 15-minute timeout (video can take 10min)  # 5-minute timeout
                    if event_str is None:
                        break
                    yield f"data: {event_str}\n\n"
            except queue.Empty:
                # Timeout — send a final event
                timeout_event = json.dumps({
                    "stage": "pipeline", "status": "error",
                    "message": "Stream timed out",
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })
                yield f"data: {timeout_event}\n\n"
            finally:
                # Clean up this queue from active streams
                with streams_lock:
                    if content_id in active_streams:
                        try:
                            active_streams[content_id].remove(event_queue)
                        except ValueError:
                            pass
                        if not active_streams[content_id]:
                            del active_streams[content_id]

        response = Response(stream(), mimetype="text/event-stream")
        response.headers["Cache-Control"] = "no-cache"
        response.headers["X-Accel-Buffering"] = "no"  # Disable nginx buffering
        response.headers["X-Content-Id"] = str(content_id)
        return response

    @app.route("/api/stream/<int:item_id>")
    @login_required
    def api_stream(item_id):
        """
        Reconnect to an active SSE stream for a content item.
        If the pipeline is still running, the client will receive remaining events.
        If it's done, send the current state as a single event.
        """
        event_queue = queue.Queue()

        with streams_lock:
            if item_id in active_streams:
                # Pipeline is still running — join the stream
                active_streams[item_id].append(event_queue)
            else:
                # Pipeline is done — send current state
                item = get_content_item(item_id)
                if item:
                    state_event = json.dumps({
                        "stage": "pipeline",
                        "status": "reconnected",
                        "message": f"Current status: {item['status']}",
                        "detail": {"current_status": item["status"]},
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "content_id": item_id
                    })
                    event_queue.put(state_event)
                event_queue.put(None)

        def stream():
            try:
                while True:
                    event_str = event_queue.get(timeout=900)  # 15-minute timeout (video can take 10min)
                    if event_str is None:
                        break
                    yield f"data: {event_str}\n\n"
            except queue.Empty:
                pass
            finally:
                with streams_lock:
                    if item_id in active_streams:
                        try:
                            active_streams[item_id].remove(event_queue)
                        except ValueError:
                            pass

        response = Response(stream(), mimetype="text/event-stream")
        response.headers["Cache-Control"] = "no-cache"
        response.headers["X-Accel-Buffering"] = "no"
        return response

    @app.route("/api/publish/<int:item_id>", methods=["POST"])
    @login_required
    def api_publish(item_id):
        """
        Trigger publishing for a ready content item.
        Returns an SSE stream for the publish stage.
        """
        item = get_content_item(item_id)
        if not item:
            return jsonify({"error": "Not found"}), 404

        event_queue = queue.Queue()

        def publish():
            def emit_event(stage, status, message, detail=None):
                event_data = {
                    "stage": stage, "status": status,
                    "message": message, "detail": detail or {},
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "content_id": item_id
                }
                event_queue.put(json.dumps(event_data))

            stage_publish(item_id, emit_event)
            event_queue.put(None)

        thread = threading.Thread(target=publish, daemon=True)
        thread.start()

        def stream():
            try:
                while True:
                    event_str = event_queue.get(timeout=60)
                    if event_str is None:
                        break
                    yield f"data: {event_str}\n\n"
            except queue.Empty:
                pass

        response = Response(stream(), mimetype="text/event-stream")
        response.headers["Cache-Control"] = "no-cache"
        response.headers["X-Accel-Buffering"] = "no"
        return response

    @app.route("/api/regenerate-image/<int:item_id>", methods=["POST"])
    @login_required
    def api_regenerate_image(item_id):
        """
        Regenerate the image for a content item with an edited prompt.
        Returns an SSE stream for the image regeneration.
        """
        data = request.json or {}
        new_prompt = data.get("prompt", "").strip()

        item = get_content_item(item_id)
        if not item:
            return jsonify({"error": "Not found"}), 404

        if not new_prompt:
            new_prompt = item.get("image_prompt", "A beautiful image")

        event_queue = queue.Queue()

        def regen():
            def emit_event(stage, status, message, detail=None):
                event_data = {
                    "stage": stage, "status": status,
                    "message": message, "detail": detail or {},
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "content_id": item_id
                }
                event_queue.put(json.dumps(event_data))

            regenerate_image(item_id, new_prompt, emit_event)
            event_queue.put(None)

        thread = threading.Thread(target=regen, daemon=True)
        thread.start()

        def stream():
            try:
                while True:
                    event_str = event_queue.get(timeout=180)
                    if event_str is None:
                        break
                    yield f"data: {event_str}\n\n"
            except queue.Empty:
                pass

        response = Response(stream(), mimetype="text/event-stream")
        response.headers["Cache-Control"] = "no-cache"
        response.headers["X-Accel-Buffering"] = "no"
        return response

    return app


# ===========================================================================
# RUN THE APP
# ===========================================================================

# Create the app instance (used by gunicorn: gunicorn app:app)
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"\n  Content Automation Demo running at http://localhost:{port}\n")
    app.run(debug=True, port=port, threaded=True)
