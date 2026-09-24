"""AI Predictive Maintenance System — one Flask app.

  * serves the web pages (templates/ + static/)
  * serves the JSON API under /api/... (routes/), which the pages call with fetch()

Run:  python app.py      then open http://localhost:5000
"""
import datetime
import decimal

import mysql.connector
from flask import Flask, jsonify, render_template, request
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS

from config import Config
from database import run_query
from utils.validation import ValidationError

from routes.auth import auth_bp
from routes.users import users_bp
from routes.equipment import equipment_bp
from routes.maintenance import maintenance_bp
from routes.prediction import prediction_bp
from routes.alerts import alerts_bp
from routes.history import history_bp
from routes.dashboard import dashboard_bp, reports_bp


class ApiJSONProvider(DefaultJSONProvider):
    """Dates go out as ISO-8601 ('2026-09-18', '2026-09-18T14:30:00') instead of
    Flask's default 'Fri, 18 Sep 2026 00:00:00 GMT', which is awkward to use in JavaScript."""

    @staticmethod
    def default(o):
        if isinstance(o, (datetime.datetime, datetime.date)):
            return o.isoformat()
        if isinstance(o, decimal.Decimal):
            return float(o)
        return DefaultJSONProvider.default(o)

    sort_keys = False


def create_app():
    app = Flask(__name__)
    app.json = ApiJSONProvider(app)

    # The pages are served by this same app (same origin), so CORS is only needed
    # if you point a separate front end (e.g. a React dev server) at the API.
    CORS(app, origins=Config.CORS_ORIGINS, supports_credentials=True)

    if Config.JWT_SECRET == "dev-secret-change-me":
        app.logger.warning("JWT_SECRET is the built-in default. Set a long random value in .env before deploying.")

    # ---------------------------------------------------------------- API
    for bp in (auth_bp, users_bp, equipment_bp, maintenance_bp, prediction_bp,
               alerts_bp, history_bp, dashboard_bp, reports_bp):
        app.register_blueprint(bp)

    @app.get("/api/health")
    def health():
        try:
            run_query("SELECT 1", fetch_one=True)
            database = "up"
        except mysql.connector.Error:
            database = "down"
        return jsonify({"status": "ok", "database": database})

    # -------------------------------------------------------------- Pages
    # These only serve HTML shells; every piece of data on them comes from the
    # API, which requires a login token. static/js/api.js sends visitors without
    # a token back to the login page.
    @app.route("/")
    @app.route("/login")
    def login():
        return render_template("login.html")

    @app.route("/dashboard")
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/equipment")
    def equipment():
        return render_template("equipment.html")

    @app.route("/prediction")
    def prediction():
        return render_template("prediction.html")

    @app.route("/maintenance")
    def maintenance():
        return render_template("maintenance.html")

    @app.route("/reports")
    def reports():
        return render_template("reports.html")

    @app.route("/history")
    def history():
        return render_template("history.html")

    @app.route("/users")
    def users():
        return render_template("users.html")

    @app.route("/alerts")
    def alerts():
        return render_template("alerts.html")

    # ------------------------------------------------------------- Errors
    @app.errorhandler(ValidationError)
    def bad_request(e):
        return jsonify({"error": str(e)}), 400

    @app.errorhandler(mysql.connector.Error)
    def database_error(e):
        app.logger.exception("Database error")
        errno = getattr(e, "errno", None)
        if isinstance(e, mysql.connector.IntegrityError):
            return jsonify({"error": "That change conflicts with existing data."}), 409
        if errno in (1054, 1146):   # unknown column / table
            return jsonify({"error": "The database is out of date. Run `python setup_db.py` and restart."}), 500
        if isinstance(e, (mysql.connector.InterfaceError, mysql.connector.errors.PoolError)) \
                or errno in (2002, 2003, 2006, 2013, 1045, 1049):
            return jsonify({"error": "Cannot reach the database. Check that MySQL is running "
                                     "(XAMPP) and the DB_* values in .env are correct."}), 503
        return jsonify({"error": "Database error"}), 500

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found"}), 404
        return "<h1>404</h1><p>Page not found. <a href='/'>Back to login</a></p>", 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def server_error(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error"}), 500
        return "<h1>500</h1><p>Something went wrong on the server.</p>", 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=Config.DEBUG, port=5000)
