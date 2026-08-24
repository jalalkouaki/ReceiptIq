import os
from flask import Flask, render_template, send_from_directory, redirect, request
from config import load_settings
from database import init_db, get_db_session
from seed import seed_database
from logger import setup_logger, log_event
from routes.auth_routes import auth_bp
from routes.admin_routes import admin_bp
from routes.receipt_routes import receipt_bp
from routes.category_routes import category_bp
from routes.warranty_routes import warranty_bp
from routes.subscription_routes import subscription_bp
from routes.inventory_routes import inventory_bp
from routes.price_history_routes import price_history_bp
from routes.report_routes import report_bp
from routes.setting_routes import setting_bp
from routes.generator_routes import generator_bp


def create_app():
    cfg = load_settings()
    setup_logger(cfg.get("LOGS_DIR"))

    encryption_key = os.environ.get("ENCRYPTION_KEY") or cfg.get("ENCRYPTION_KEY")
    if not encryption_key:
        log_event("server", "Flask server failed to start: missing ENCRYPTION_KEY environment variable", level="CRITICAL")
        raise RuntimeError("ENCRYPTION_KEY environment variable is required to start Flask server.")

    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["SECRET_KEY"] = cfg.get("SECRET_KEY", "receiptiq-jwt-secret-local-only-key")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload

    # Initialize encrypted database connection & seed data
    try:
        engine, session_factory = init_db(db_path=cfg.get("DB_PATH"), encryption_key=encryption_key)
        db = session_factory()
        seed_database(db)
        db.close()
    except Exception as e:
        log_event("server", f"Failed to initialize database: {e}", level="CRITICAL")
        raise e

    # Register API Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(receipt_bp)
    app.register_blueprint(category_bp)
    app.register_blueprint(warranty_bp)
    app.register_blueprint(subscription_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(price_history_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(setting_bp)
    app.register_blueprint(generator_bp)

    # Web UI Page Routes
    @app.route("/")
    def index():
        return redirect("/dashboard")

    @app.route("/login")
    def login_page():
        return render_template("login.html")

    @app.route("/dashboard")
    @app.route("/user")
    def dashboard_page():
        return render_template("dashboard.html")

    @app.route("/admin")
    def admin_page():
        return render_template("admin.html")

    @app.route("/receipts")
    def receipts_page():
        return render_template("receipts.html")

    @app.route("/receipts/<int:receipt_id>")
    def receipt_detail_page(receipt_id):
        return render_template("receipt_detail.html", receipt_id=receipt_id)

    @app.route("/warranties")
    def warranties_page():
        return render_template("warranties.html")

    @app.route("/subscriptions")
    def subscriptions_page():
        return render_template("subscriptions.html")

    @app.route("/inventory")
    def inventory_page():
        return render_template("inventory.html")

    @app.route("/price-history")
    def price_history_page():
        return render_template("price_history.html")

    @app.route("/reports")
    def reports_page():
        return render_template("reports.html")

    @app.route("/generator")
    def generator_page():
        return render_template("generator.html")

    @app.route("/settings")
    def settings_page():
        return render_template("settings.html")

    @app.route("/uploads/<path:filename>")
    def serve_upload(filename):
        storage_path = cfg.get("STORAGE_PATH")
        return send_from_directory(storage_path, filename)

    log_event("server", f"Flask application created successfully (port {cfg.get('PORT')})", level="INFO")
    return app


if __name__ == "__main__":
    cfg = load_settings()
    app = create_app()
    app.run(host="127.0.0.1", port=cfg.get("PORT", 5000), debug=False)
