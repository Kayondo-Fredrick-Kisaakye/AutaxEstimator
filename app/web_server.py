import os
from datetime import datetime
from hmac import compare_digest
from secrets import token_urlsafe

import psycopg2
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from app.utils.tax_engine import DEFAULT_TAX_RULES, calculate_ura_car_tax


app = Flask(__name__)
secret_key = os.environ.get("SECRET_KEY")
if not secret_key and os.environ.get("FLASK_ENV") == "production":
    raise RuntimeError("SECRET_KEY must be configured in production.")
app.config["SECRET_KEY"] = secret_key or "autax-estimator-development-key"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE") == "1"


@app.after_request
def add_security_headers(response):
    # C. Apply browser protections for the server-rendered application
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; form-action 'self'; "
        "frame-ancestors 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.context_processor
def inject_security_helpers():
    # A. Make the CSRF token available to every server-rendered form
    session.setdefault("csrf_token", token_urlsafe(32))
    return {"csrf_token": session["csrf_token"]}


@app.before_request
def protect_post_requests():
    # B. Reject forged form submissions outside the test environment
    if request.method == "POST" and not app.config.get("TESTING"):
        expected_token = session.get("csrf_token", "")
        submitted_token = request.form.get("csrf_token", "")
        if (
            not expected_token
            or not submitted_token
            or not compare_digest(expected_token, submitted_token)
        ):
            abort(400, description="Invalid form security token.")


def get_db_connection():
    # A. Open the configured PostgreSQL connection
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured.")
    return psycopg2.connect(database_url)


def get_latest_currency_rate():
    connection = None

    # C. Read the newest successful currency rate from the cache
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT rate, source, fetched_at
                FROM currency_rates
                WHERE base_currency = 'USD' AND quote_currency = 'UGX'
                ORDER BY fetched_at DESC
                LIMIT 1
                """
            )
            return cursor.fetchone()
    except (RuntimeError, psycopg2.Error):
        return None
    finally:
        if connection:
            connection.close()


def get_current_tax_rules():
    connection = None

    # D. Load the latest effective rules and keep safe defaults as fallback
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT import_duty_rate, excise_duty_rate, vat_rate,
                       environmental_levy_rate, withholding_tax_rate,
                       infrastructure_levy_rate, idf_rate, fixed_fees_ugx,
                       age_limit_years, environmental_levy_age
                FROM tax_rules
                ORDER BY effective_from DESC, id DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            if row:
                names = tuple(DEFAULT_TAX_RULES)
                return dict(zip(names, row))
    except (RuntimeError, psycopg2.Error):
        pass
    finally:
        if connection:
            connection.close()
    return DEFAULT_TAX_RULES.copy()


def save_calculation(user_id, form_data, breakdown):
    connection = None

    # B. Save the approved calculation against the signed-in user
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO tax_calculations (
                    user_id,
                    custom_purchase_price_usd,
                    calculated_import_duty_ugx,
                    calculated_excise_duty_ugx,
                    calculated_vat_ugx,
                    calculated_env_levy_ugx,
                    total_tax_payable_ugx,
                    engine_cc,
                    year_of_manufacture,
                    usd_to_ugx_rate
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    form_data["cif_usd"],
                    breakdown["import_duty_ugx"],
                    breakdown["excise_duty_ugx"],
                    breakdown["vat_ugx"],
                    breakdown["environmental_levy_ugx"],
                    breakdown["total_payable_to_ura_ugx"],
                    form_data["engine_cc"],
                    form_data["year_of_manufacture"],
                    form_data["usd_to_ugx_rate"],
                ),
            )
        connection.commit()
    finally:
        if connection:
            connection.close()


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    # A. Provide a lightweight deployment health check
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return {"status": "ok", "database": "ok"}, 200
    except (RuntimeError, psycopg2.Error):
        return {"status": "degraded", "database": "unavailable"}, 503
    finally:
        if connection:
            connection.close()


@app.route("/estimate", methods=["GET", "POST"])
def estimate():
    result = None
    error = None
    form_data = request.form if request.method == "POST" else {}
    rate_info = get_latest_currency_rate()
    default_rate = (
        rate_info[0] if rate_info else os.environ.get("DEFAULT_USD_TO_UGX_RATE", "")
    )

    # A. Receive the estimator inputs and calculate the tax result
    if request.method == "POST":
        try:
            result = calculate_ura_car_tax(
                request.form.get("cif_usd", ""),
                request.form.get("engine_cc", ""),
                request.form.get("year_of_manufacture", ""),
                request.form.get("usd_to_ugx_rate") or default_rate,
                get_current_tax_rules(),
            )

            # B. Keep a successful calculation for signed-in users
            if result["status"] == "APPROVED" and session.get("user_id"):
                try:
                    save_calculation(
                        session["user_id"], request.form, result["breakdown"]
                    )
                except (RuntimeError, psycopg2.Error):
                    flash("Estimate completed, but it could not be saved to history.")
        except (TypeError, ValueError) as exc:
            error = str(exc)

    return render_template(
        "estimate.html",
        current_year=datetime.now().year,
        error=error,
        form_data=form_data,
        default_rate=default_rate,
        rate_info=rate_info,
        result=result,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # A. Check the submitted credentials against the user table
        connection = None
        try:
            connection = get_db_connection()
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, password_hash FROM users WHERE username = %s",
                    (username,),
                )
                user = cursor.fetchone()
        except (RuntimeError, psycopg2.Error):
            flash("Login is unavailable until PostgreSQL is configured.")
            return redirect(url_for("login"))
        finally:
            if connection:
                connection.close()

        if user and check_password_hash(user[1], password):
            session["user_id"] = user[0]
            session["username"] = username
            return redirect(url_for("estimate"))

        flash("Invalid username or password.")
        return redirect(url_for("login"))
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        bond_name = request.form.get("bond_name", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # A. Validate the account details before creating the user
        if not bond_name or not username or not password:
            flash("Bond name, username, and password are required.")
            return redirect(url_for("register"))

        connection = None
        try:
            connection = get_db_connection()
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (bond_name, username, password_hash)
                    VALUES (%s, %s, %s)
                    """,
                    (bond_name, username, generate_password_hash(password)),
                )
            connection.commit()
        except psycopg2.errors.UniqueViolation:
            if connection:
                connection.rollback()
            flash("That username is already registered.")
            return redirect(url_for("register"))
        except (RuntimeError, psycopg2.Error):
            flash("Registration is unavailable until PostgreSQL is configured.")
            return redirect(url_for("register"))
        finally:
            if connection:
                connection.close()

        flash("Account created. You can now log in.")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.get("/logout")
def logout():
    # A. End the current signed-in session
    session.clear()
    return redirect(url_for("index"))


@app.get("/history")
def history():
    if not session.get("user_id"):
        flash("Please log in to view calculation history.")
        return redirect(url_for("login"))

    calculations = []
    connection = None

    # B. Load the signed-in user's historic calculations
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT custom_purchase_price_usd, engine_cc,
                       year_of_manufacture, total_tax_payable_ugx, created_at
                FROM tax_calculations
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (session["user_id"],),
            )
            calculations = cursor.fetchall()
    except (RuntimeError, psycopg2.Error):
        flash("Calculation history is unavailable until PostgreSQL is configured.")
    finally:
        if connection:
            connection.close()

    return render_template("history.html", calculations=calculations)


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
