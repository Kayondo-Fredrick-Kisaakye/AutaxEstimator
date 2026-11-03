import os
from datetime import datetime

import psycopg2
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.utils.tax_engine import calculate_ura_car_tax


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "autax-estimator-development-key"
)


def get_db_connection():
    # A. Open the configured PostgreSQL connection
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured.")
    return psycopg2.connect(database_url)


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


@app.route("/estimate", methods=["GET", "POST"])
def estimate():
    result = None
    error = None
    form_data = request.form if request.method == "POST" else {}

    # A. Receive the estimator inputs and calculate the tax result
    if request.method == "POST":
        try:
            result = calculate_ura_car_tax(
                request.form.get("cif_usd", ""),
                request.form.get("engine_cc", ""),
                request.form.get("year_of_manufacture", ""),
                request.form.get("usd_to_ugx_rate", ""),
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
        result=result,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # A. Check the submitted credentials against the user table
        try:
            connection = get_db_connection()
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, password_hash FROM users WHERE username = %s",
                    (username,),
                )
                user = cursor.fetchone()
            connection.close()
        except (RuntimeError, psycopg2.Error):
            flash("Login is unavailable until PostgreSQL is configured.")
            return redirect(url_for("login"))

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
