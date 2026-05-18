"""Razorpay deposits + webhook with signature verification & idempotency."""
import hmac, hashlib, json
from decimal import Decimal
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, current_app, jsonify, abort)
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Deposit
from ..utils import credit

bp = Blueprint("payments", __name__, template_folder="../templates/payments")

try:
    import razorpay
except Exception:
    razorpay = None


def _client():
    kid = current_app.config.get("RAZORPAY_KEY_ID")
    secret = current_app.config.get("RAZORPAY_KEY_SECRET")
    if not (razorpay and kid and secret):
        return None
    return razorpay.Client(auth=(kid, secret))


@bp.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    if request.method == "POST":
        try:
            amount = Decimal(request.form.get("amount", "0"))
        except Exception:
            amount = Decimal("0")
        if amount < current_app.config["MIN_DEPOSIT"]:
            flash(f"Minimum deposit is ₹{current_app.config['MIN_DEPOSIT']}.", "danger")
            return redirect(url_for("payments.deposit"))
        dep = Deposit(user_id=current_user.id, amount=amount, status="pending")
        db.session.add(dep); db.session.commit()
        cli = _client()
        if not cli:
            # Dev / sandbox mode: auto-credit
            dep.status = "success"; dep.payment_id = f"DEV{dep.id}"
            db.session.commit()
            credit(current_user.id, amount, wallet_type="main", tx_type="deposit",
                   reference=dep.payment_id, idem=f"dep_{dep.id}")
            flash(f"DEV mode: ₹{amount} credited.", "success")
            return redirect(url_for("wallet.dashboard"))
        order = cli.order.create({"amount": int(amount * 100), "currency": "INR",
                                  "receipt": f"dep_{dep.id}", "payment_capture": 1})
        dep.order_id = order["id"]; db.session.commit()
        return render_template("payments/checkout.html", order=order, deposit=dep,
                               key_id=current_app.config["RAZORPAY_KEY_ID"])
    return render_template("payments/deposit.html",
                           min_amount=current_app.config["MIN_DEPOSIT"])


@bp.route("/verify", methods=["POST"])
@login_required
def verify():
    """Client-side Razorpay handler posts here after success."""
    cli = _client()
    if not cli:
        return jsonify(ok=False, error="provider_disabled"), 400
    payload = request.get_json() or {}
    try:
        cli.utility.verify_payment_signature({
            "razorpay_order_id": payload["razorpay_order_id"],
            "razorpay_payment_id": payload["razorpay_payment_id"],
            "razorpay_signature": payload["razorpay_signature"],
        })
    except Exception:
        return jsonify(ok=False, error="bad_signature"), 400
    dep = Deposit.query.filter_by(order_id=payload["razorpay_order_id"]).first_or_404()
    if dep.status != "success":
        dep.status = "success"; dep.payment_id = payload["razorpay_payment_id"]
        db.session.commit()
        credit(dep.user_id, dep.amount, wallet_type="main", tx_type="deposit",
               reference=dep.payment_id, idem=f"dep_{dep.id}")
    return jsonify(ok=True, redirect=url_for("wallet.dashboard"))


@bp.route("/webhook/razorpay", methods=["POST"])
def razorpay_webhook():
    secret = current_app.config.get("RAZORPAY_WEBHOOK_SECRET", "")
    sig = request.headers.get("X-Razorpay-Signature", "")
    body = request.get_data()
    if not secret:
        abort(400, "webhook secret missing")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        abort(400, "invalid signature")
    event = json.loads(body or b"{}")
    if event.get("event") == "payment.captured":
        pay = event["payload"]["payment"]["entity"]
        dep = Deposit.query.filter_by(order_id=pay.get("order_id")).first()
        if dep and dep.status != "success":
            dep.status = "success"; dep.payment_id = pay["id"]
            db.session.commit()
            credit(dep.user_id, dep.amount, wallet_type="main", tx_type="deposit",
                   reference=pay["id"], idem=f"dep_{dep.id}")
    return "", 200


@bp.route("/history")
@login_required
def history():
    rows = Deposit.query.filter_by(user_id=current_user.id) \
        .order_by(Deposit.id.desc()).limit(50).all()
    return render_template("payments/history.html", rows=rows)
