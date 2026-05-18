"""Security center: support page + helper endpoints (HTTPS hints, etc.)."""
from flask import Blueprint, render_template, current_app

bp = Blueprint("security", __name__, template_folder="../templates/security")


@bp.route("/support")
def support():
    return render_template("security/support.html")


@bp.route("/responsible-gaming")
def responsible():
    return render_template("security/responsible.html")
