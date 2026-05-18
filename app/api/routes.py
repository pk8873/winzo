"""REST API (JSON). Token-style auth via session for now; extend with JWT as needed."""
from decimal import Decimal
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ..extensions import db, limiter
from ..models import (User, Game, WalletTransaction, Deposit, Withdrawal,
                      wallet_balance)

bp = Blueprint("api", __name__)


@bp.route("/health")
def health():
    return jsonify(status="ok")


@bp.route("/me")
@login_required
def me():
    return jsonify(id=current_user.id, name=current_user.name,
                   email=current_user.email, mobile=current_user.mobile,
                   role=current_user.role,
                   balance=str(wallet_balance(current_user.id)))


@bp.route("/wallet/summary")
@login_required
def wallet_summary():
    return jsonify(
        main=str(wallet_balance(current_user.id, "main")),
        winning=str(wallet_balance(current_user.id, "winning")),
        bonus=str(wallet_balance(current_user.id, "bonus")),
        total=str(wallet_balance(current_user.id)),
    )


@bp.route("/wallet/transactions")
@login_required
@limiter.limit("60/minute")
def wallet_tx():
    rows = WalletTransaction.query.filter_by(user_id=current_user.id) \
        .order_by(WalletTransaction.id.desc()).limit(50).all()
    return jsonify([dict(id=t.id, type=t.tx_type, wallet=t.wallet_type,
                         amount=str(t.amount), ref=t.reference,
                         at=t.created_at.isoformat()) for t in rows])


@bp.route("/games")
@login_required
def games():
    rows = Game.query.filter_by(is_enabled=True).all()
    return jsonify([dict(code=g.code, name=g.name, category=g.category,
                         min=str(g.min_entry), max=str(g.max_entry),
                         rtp=g.rtp, round_seconds=g.round_seconds) for g in rows])
