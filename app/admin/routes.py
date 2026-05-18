from datetime import datetime
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func
from ..extensions import db
from ..models import (User, Game, Deposit, Withdrawal, GameEntry, CardRound,
                      WalletTransaction, FraudFlag, AdminLog, Notification,
                      Referral, wallet_balance)
from ..utils import admin_required, log_admin, credit, debit

bp = Blueprint("admin", __name__, template_folder="../templates/admin")


@bp.route("/")
@login_required
@admin_required()
def dashboard():
    stats = {
        "users": User.query.count(),
        "blocked": User.query.filter_by(is_blocked=True).count(),
        "deposits_total": db.session.query(func.coalesce(func.sum(Deposit.amount), 0))
            .filter_by(status="success").scalar(),
        "withdraw_pending": Withdrawal.query.filter_by(status="pending").count(),
        "fraud_open": FraudFlag.query.filter_by(resolved=False).count(),
        "games_total": Game.query.count(),
        "games_enabled": Game.query.filter_by(is_enabled=True).count(),
        "rounds_today": GameEntry.query.filter(
            GameEntry.created_at >= datetime.utcnow().date()).count(),
    }
    return render_template("admin/dashboard.html", stats=stats)


@bp.route("/users")
@login_required
@admin_required()
def users():
    q = request.args.get("q", "").strip()
    query = User.query
    if q:
        query = query.filter((User.email.ilike(f"%{q}%")) | (User.mobile.ilike(f"%{q}%"))
                             | (User.name.ilike(f"%{q}%")))
    rows = query.order_by(User.id.desc()).limit(200).all()
    return render_template("admin/users.html", rows=rows, q=q,
                           balances={u.id: wallet_balance(u.id) for u in rows})


@bp.route("/users/<int:uid>/block", methods=["POST"])
@login_required
@admin_required()
def block_user(uid):
    u = User.query.get_or_404(uid)
    u.is_blocked = not u.is_blocked
    db.session.commit()
    log_admin("toggle_block", uid, f"is_blocked={u.is_blocked}")
    flash(f"User {'blocked' if u.is_blocked else 'unblocked'}.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:uid>/adjust", methods=["POST"])
@login_required
@admin_required(roles=("super_admin", "finance_admin"))
def adjust_wallet(uid):
    amt = Decimal(request.form.get("amount", "0"))
    wt = request.form.get("wallet_type", "main")
    note = request.form.get("note", "")
    if amt > 0:
        credit(uid, amt, wallet_type=wt, tx_type="admin_adjust",
               reference=f"admin:{current_user.id}", meta=note)
    elif amt < 0:
        debit(uid, -amt, wallet_type=wt, tx_type="admin_adjust",
              reference=f"admin:{current_user.id}", meta=note, allow_overdraft=True)
    log_admin("wallet_adjust", uid, f"{amt} {wt} :: {note}")
    flash("Wallet adjusted.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/withdrawals")
@login_required
@admin_required()
def withdrawals():
    status = request.args.get("status", "pending")
    rows = Withdrawal.query.filter_by(status=status).order_by(Withdrawal.id.desc()).all()
    return render_template("admin/withdrawals.html", rows=rows, status=status)


@bp.route("/withdrawals/<int:wid>/decide", methods=["POST"])
@login_required
@admin_required(roles=("super_admin", "finance_admin"))
def decide_withdraw(wid):
    wd = Withdrawal.query.get_or_404(wid)
    decision = request.form.get("decision")
    note = request.form.get("note", "")
    if wd.status != "pending":
        flash("Already decided.", "warning")
        return redirect(url_for("admin.withdrawals"))
    if decision == "approve":
        wd.status = "paid"
    elif decision == "reject":
        wd.status = "rejected"
        # refund reserved amount
        credit(wd.user_id, wd.amount, wallet_type="main", tx_type="admin_adjust",
               reference=f"refund_wd:{wd.id}", idem=f"refund_wd_{wd.id}",
               meta="withdrawal rejected")
    wd.admin_note = note; wd.decided_at = datetime.utcnow()
    db.session.commit()
    log_admin("withdraw_decision", wid, f"{decision} :: {note}")
    flash(f"Withdrawal {decision}d.", "success")
    return redirect(url_for("admin.withdrawals"))


@bp.route("/deposits")
@login_required
@admin_required()
def deposits():
    rows = Deposit.query.order_by(Deposit.id.desc()).limit(200).all()
    return render_template("admin/deposits.html", rows=rows)


@bp.route("/games")
@login_required
@admin_required()
def games():
    rows = Game.query.order_by(Game.id).all()
    return render_template("admin/games.html", rows=rows)


@bp.route("/games/<int:gid>/update", methods=["POST"])
@login_required
@admin_required()
def update_game(gid):
    g = Game.query.get_or_404(gid)
    g.is_enabled = request.form.get("enabled") == "on"
    try:
        g.rtp = float(request.form.get("rtp", g.rtp))
        g.min_entry = Decimal(request.form.get("min_entry", g.min_entry))
        g.max_entry = Decimal(request.form.get("max_entry", g.max_entry))
        g.round_seconds = int(request.form.get("round_seconds", g.round_seconds or 60))
    except Exception:
        pass
    db.session.commit()
    log_admin("game_update", g.code,
              f"enabled={g.is_enabled} rtp={g.rtp} min={g.min_entry} max={g.max_entry}")
    flash("Game updated.", "success")
    return redirect(url_for("admin.games"))


@bp.route("/fraud")
@login_required
@admin_required()
def fraud():
    rows = FraudFlag.query.order_by(FraudFlag.id.desc()).limit(200).all()
    return render_template("admin/fraud.html", rows=rows)


@bp.route("/fraud/<int:fid>/resolve", methods=["POST"])
@login_required
@admin_required()
def resolve_fraud(fid):
    f = FraudFlag.query.get_or_404(fid)
    f.resolved = True; db.session.commit()
    log_admin("fraud_resolve", fid, "")
    flash("Flag resolved.", "success")
    return redirect(url_for("admin.fraud"))


@bp.route("/logs")
@login_required
@admin_required()
def logs():
    rows = AdminLog.query.order_by(AdminLog.id.desc()).limit(300).all()
    return render_template("admin/logs.html", rows=rows)


@bp.route("/broadcast", methods=["GET", "POST"])
@login_required
@admin_required()
def broadcast():
    if request.method == "POST":
        title = request.form.get("title", "Announcement")
        body = request.form.get("body", "")
        db.session.add(Notification(user_id=None, title=title, body=body))
        db.session.commit()
        log_admin("broadcast", "", title)
        flash("Notification sent to all users.", "success")
        return redirect(url_for("admin.broadcast"))
    return render_template("admin/broadcast.html")


@bp.route("/analytics")
@login_required
@admin_required()
def analytics():
    revenue = db.session.query(
        func.coalesce(func.sum(GameEntry.amount), 0)).scalar()
    paid_out = db.session.query(
        func.coalesce(func.sum(GameEntry.payout), 0)).scalar()
    card_rev = db.session.query(
        func.coalesce(func.sum(CardRound.amount), 0)).scalar()
    card_paid = db.session.query(
        func.coalesce(func.sum(CardRound.payout), 0)).scalar()
    referrals = Referral.query.count()
    return render_template("admin/analytics.html",
                           revenue=revenue, paid_out=paid_out,
                           card_rev=card_rev, card_paid=card_paid,
                           ggr=(revenue + card_rev) - (paid_out + card_paid),
                           referrals=referrals)
