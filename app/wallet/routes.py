from flask import Blueprint, render_template
from flask_login import login_required, current_user
from ..models import (WalletTransaction, Deposit, Withdrawal, GameEntry,
                      CardRound, Notification, wallet_balance)

bp = Blueprint("wallet", __name__, template_folder="../templates/wallet")


@bp.route("/dashboard")
@login_required
def dashboard():
    main = wallet_balance(current_user.id, "main")
    winning = wallet_balance(current_user.id, "winning")
    bonus = wallet_balance(current_user.id, "bonus")
    recent_tx = WalletTransaction.query.filter_by(user_id=current_user.id) \
        .order_by(WalletTransaction.id.desc()).limit(10).all()
    recent_entries = GameEntry.query.filter_by(user_id=current_user.id) \
        .order_by(GameEntry.id.desc()).limit(5).all()
    recent_cards = CardRound.query.filter_by(user_id=current_user.id) \
        .order_by(CardRound.id.desc()).limit(5).all()
    notifs = Notification.query.filter(
        (Notification.user_id == current_user.id) | (Notification.user_id == None)  # noqa
    ).order_by(Notification.id.desc()).limit(5).all()
    return render_template("wallet/dashboard.html",
                           main=main, winning=winning, bonus=bonus,
                           total=main + winning + bonus,
                           recent_tx=recent_tx,
                           recent_entries=recent_entries,
                           recent_cards=recent_cards,
                           notifs=notifs)


@bp.route("/history")
@login_required
def history():
    tx = WalletTransaction.query.filter_by(user_id=current_user.id) \
        .order_by(WalletTransaction.id.desc()).limit(200).all()
    return render_template("wallet/history.html", tx=tx)
