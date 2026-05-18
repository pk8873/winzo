from decimal import Decimal
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Withdrawal, wallet_balance
from ..utils import debit, flag_fraud

bp = Blueprint("withdraw", __name__, template_folder="../templates/withdraw")


@bp.route("/", methods=["GET", "POST"])
@login_required
def request_withdraw():
    cooldown = current_app.config.get("WITHDRAW_COOLDOWN_MINUTES", 30)
    last = Withdrawal.query.filter_by(user_id=current_user.id) \
        .order_by(Withdrawal.id.desc()).first()
    if request.method == "POST":
        if last and last.created_at > datetime.utcnow() - timedelta(minutes=cooldown):
            flash(f"Please wait {cooldown} min between withdrawals.", "warning")
            return redirect(url_for("withdraw.request_withdraw"))
        try:
            amount = Decimal(request.form.get("amount", "0"))
        except Exception:
            amount = Decimal("0")
        if amount < current_app.config["MIN_WITHDRAW"]:
            flash(f"Minimum withdrawal is ₹{current_app.config['MIN_WITHDRAW']}.", "danger")
            return redirect(url_for("withdraw.request_withdraw"))
        bal = wallet_balance(current_user.id)
        if amount > bal:
            flash("Insufficient balance.", "danger")
            return redirect(url_for("withdraw.request_withdraw"))
        method = request.form.get("method", "upi")
        wd = Withdrawal(user_id=current_user.id, amount=amount, method=method,
                        upi_id=request.form.get("upi_id"),
                        bank_account=request.form.get("bank_account"),
                        ifsc=request.form.get("ifsc"),
                        account_holder=request.form.get("account_holder"))
        # Reserve funds immediately from winning then main
        win_bal = wallet_balance(current_user.id, "winning")
        remaining = amount
        if win_bal > 0:
            take = min(win_bal, remaining)
            debit(current_user.id, take, wallet_type="winning",
                  tx_type="withdraw", reference="pending", idem=f"wdW_{datetime.utcnow().timestamp()}")
            remaining -= take
        if remaining > 0:
            debit(current_user.id, remaining, wallet_type="main",
                  tx_type="withdraw", reference="pending", idem=f"wdM_{datetime.utcnow().timestamp()}")
        db.session.add(wd); db.session.commit()
        # Suspicious check: large withdraw soon after deposit
        if amount >= Decimal("10000"):
            flag_fraud(current_user.id, "large_withdraw", "medium", f"₹{amount}")
        flash("Withdrawal request submitted. Awaiting admin approval.", "success")
        return redirect(url_for("withdraw.history"))
    return render_template("withdraw/request.html", balance=wallet_balance(current_user.id))


@bp.route("/history")
@login_required
def history():
    rows = Withdrawal.query.filter_by(user_id=current_user.id) \
        .order_by(Withdrawal.id.desc()).all()
    return render_template("withdraw/history.html", rows=rows)
