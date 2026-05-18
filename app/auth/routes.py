from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
from ..extensions import db, limiter
from ..models import User
from ..utils import (issue_otp, verify_otp, gen_referral_code,
                     detect_multi_account, client_ip)

bp = Blueprint("auth", __name__, template_folder="../templates/auth")


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("20/hour")
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        mobile = request.form.get("mobile", "").strip()
        password = request.form.get("password", "")
        ref = request.form.get("ref", "").strip().upper()
        if not (name and email and mobile and len(password) >= 6):
            flash("Please fill all fields (password ≥ 6 chars).", "danger")
            return redirect(url_for("auth.register"))
        if User.query.filter((User.email == email) | (User.mobile == mobile)).first():
            flash("Email or mobile already in use.", "danger")
            return redirect(url_for("auth.register"))
        u = User(name=name, email=email, mobile=mobile,
                 referral_code=gen_referral_code())
        u.set_password(password)
        if ref:
            r = User.query.filter_by(referral_code=ref).first()
            if r:
                u.referred_by_id = r.id
        db.session.add(u)
        db.session.commit()
        issue_otp(mobile, "register")
        flash("Account created. Verify your mobile with the OTP.", "success")
        return redirect(url_for("auth.verify", mobile=mobile))
    return render_template("auth/register.html")


@bp.route("/verify", methods=["GET", "POST"])
def verify():
    mobile = request.values.get("mobile", "")
    if request.method == "POST":
        code = request.form.get("code", "")
        if verify_otp(mobile, code, "register"):
            u = User.query.filter_by(mobile=mobile).first()
            if u:
                u.is_verified = True
                db.session.commit()
                login_user(u)
                flash("Mobile verified. Welcome!", "success")
                return redirect(url_for("wallet.dashboard"))
        flash("Invalid or expired OTP.", "danger")
    return render_template("auth/verify.html", mobile=mobile)


@bp.route("/resend-otp", methods=["POST"])
@limiter.limit("5/minute")
def resend():
    mobile = request.form.get("mobile", "")
    purpose = request.form.get("purpose", "register")
    if mobile:
        issue_otp(mobile, purpose)
        flash("OTP re-sent.", "info")
    return redirect(request.referrer or url_for("home"))


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("30/hour")
def login():
    if request.method == "POST":
        ident = request.form.get("identifier", "").strip().lower()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))
        u = User.query.filter((User.email == ident) | (User.mobile == ident)).first()
        if u and u.locked_until and u.locked_until > datetime.utcnow():
            flash("Account temporarily locked. Try later.", "danger")
            return redirect(url_for("auth.login"))
        if not u or not u.check_password(password):
            if u:
                u.failed_attempts = (u.failed_attempts or 0) + 1
                if u.failed_attempts >= 5:
                    u.locked_until = datetime.utcnow() + timedelta(minutes=15)
                    u.failed_attempts = 0
                db.session.commit()
            flash("Invalid credentials.", "danger")
            return redirect(url_for("auth.login"))
        if u.is_blocked:
            flash("Account blocked. Contact support.", "danger")
            return redirect(url_for("auth.login"))
        u.failed_attempts = 0
        u.last_login_ip = client_ip()
        db.session.commit()
        detect_multi_account(u, u.last_login_ip)
        login_user(u, remember=remember)
        flash("Logged in.", "success")
        return redirect(url_for("admin.dashboard") if u.is_admin()
                        else url_for("wallet.dashboard"))
    return render_template("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("home"))


@bp.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        mobile = request.form.get("mobile", "").strip()
        if User.query.filter_by(mobile=mobile).first():
            issue_otp(mobile, "reset")
        flash("If the mobile exists, an OTP has been sent.", "info")
        return redirect(url_for("auth.reset", mobile=mobile))
    return render_template("auth/forgot.html")


@bp.route("/reset", methods=["GET", "POST"])
def reset():
    mobile = request.values.get("mobile", "")
    if request.method == "POST":
        code = request.form.get("code", "")
        pw = request.form.get("password", "")
        if len(pw) < 6:
            flash("Password too short.", "danger")
            return redirect(url_for("auth.reset", mobile=mobile))
        if verify_otp(mobile, code, "reset"):
            u = User.query.filter_by(mobile=mobile).first()
            if u:
                u.set_password(pw)
                db.session.commit()
                flash("Password updated. Please log in.", "success")
                return redirect(url_for("auth.login"))
        flash("Invalid or expired OTP.", "danger")
    return render_template("auth/reset.html", mobile=mobile)


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.name = request.form.get("name", current_user.name)
        db.session.commit()
        flash("Profile updated.", "success")
    return render_template("auth/profile.html")
