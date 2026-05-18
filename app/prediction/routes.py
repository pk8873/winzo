"""Color & Number prediction with 60s rounds (admin-controlled RTP)."""
from datetime import datetime, timedelta
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Game, PredictionRound, GameEntry, wallet_balance
from ..utils import (rand_int, rand_choice, debit, credit, gen_idem_key,
                     detect_abnormal_win)

bp = Blueprint("prediction", __name__, template_folder="../templates/prediction")

COLORS = ["red", "green", "violet"]
COLOR_PAYOUT = {"red": Decimal("2"), "green": Decimal("2"), "violet": Decimal("4.5")}
NUMBER_PAYOUT = Decimal("9")  # 9x


def _current_round(game):
    rnd = PredictionRound.query.filter_by(game_id=game.id, status="open") \
        .order_by(PredictionRound.id.desc()).first()
    now = datetime.utcnow()
    if rnd and rnd.ends_at <= now:
        _settle(game, rnd)
        rnd = None
    if not rnd:
        period = now.strftime(f"{game.code}-%Y%m%d%H%M%S")
        rnd = PredictionRound(game_id=game.id, period_code=period,
                              starts_at=now,
                              ends_at=now + timedelta(seconds=game.round_seconds or 60),
                              status="open")
        db.session.add(rnd)
        db.session.commit()
    return rnd


def _settle(game, rnd):
    if rnd.status == "settled":
        return
    rnd.status = "locked"
    db.session.commit()
    # Apply RTP-biased RNG: with probability (1 - rtp) we pick the LEAST-paying outcome
    entries = GameEntry.query.filter_by(round_id=rnd.id).all()
    rtp = game.rtp or 0.9
    biased = rand_int(1, 100) > int(rtp * 100)
    if game.code == "color_pred":
        if biased and entries:
            # choose color that minimizes payout
            tallies = {c: sum(Decimal(str(e.amount)) * COLOR_PAYOUT[c]
                              for e in entries if e.pick_value == c) for c in COLORS}
            color = min(tallies, key=tallies.get)
        else:
            color = rand_choice(COLORS)
        rnd.result_color = color
        rnd.result_number = rand_int(0, 9)
    else:  # number_pred
        if biased and entries:
            tallies = {str(n): sum(Decimal(str(e.amount)) * NUMBER_PAYOUT
                                   for e in entries if e.pick_value == str(n))
                       for n in range(10)}
            num = int(min(tallies, key=tallies.get))
        else:
            num = rand_int(0, 9)
        rnd.result_number = num
        rnd.result_color = "red" if num % 2 else "green"
    # Pay winners
    for e in entries:
        win, payout = False, Decimal("0")
        if e.pick_type == "color" and e.pick_value == rnd.result_color:
            payout = Decimal(str(e.amount)) * COLOR_PAYOUT[e.pick_value]
            win = True
        elif e.pick_type == "number" and e.pick_value == str(rnd.result_number):
            payout = Decimal(str(e.amount)) * NUMBER_PAYOUT
            win = True
        e.is_win = win
        e.payout = payout
        if win:
            credit(e.user_id, payout, wallet_type="winning", tx_type="winnings",
                   reference=f"round:{rnd.id}",
                   idem=f"win_{rnd.id}_{e.id}")
            detect_abnormal_win(e.user_id, payout, e.amount)
    rnd.status = "settled"
    rnd.settled_at = datetime.utcnow()
    db.session.commit()


@bp.route("/<code>")
@login_required
def play(code):
    game = Game.query.filter_by(code=code, is_enabled=True).first_or_404()
    rnd = _current_round(game)
    history = PredictionRound.query.filter_by(game_id=game.id, status="settled") \
        .order_by(PredictionRound.id.desc()).limit(15).all()
    return render_template("prediction/play.html", game=game, rnd=rnd,
                           history=history, colors=COLORS,
                           balance=wallet_balance(current_user.id))


@bp.route("/<code>/bet", methods=["POST"])
@login_required
def bet(code):
    game = Game.query.filter_by(code=code, is_enabled=True).first_or_404()
    rnd = _current_round(game)
    if (rnd.ends_at - datetime.utcnow()).total_seconds() < 5:
        flash("Round closing — bets locked.", "warning")
        return redirect(url_for("prediction.play", code=code))
    pick_type = request.form.get("pick_type")  # color | number
    pick_value = request.form.get("pick_value", "")
    try:
        amount = Decimal(request.form.get("amount", "0"))
    except Exception:
        amount = Decimal("0")
    if amount < game.min_entry or amount > game.max_entry:
        flash("Bet outside allowed range.", "danger")
        return redirect(url_for("prediction.play", code=code))
    if pick_type == "color" and pick_value not in COLORS:
        flash("Invalid color.", "danger"); return redirect(url_for("prediction.play", code=code))
    if pick_type == "number" and pick_value not in [str(i) for i in range(10)]:
        flash("Invalid number.", "danger"); return redirect(url_for("prediction.play", code=code))
    try:
        debit(current_user.id, amount, wallet_type="main", tx_type="entry_fee",
              reference=f"round:{rnd.id}", idem=gen_idem_key("bet"))
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("prediction.play", code=code))
    db.session.add(GameEntry(round_id=rnd.id, user_id=current_user.id,
                             pick_type=pick_type, pick_value=str(pick_value),
                             amount=amount))
    db.session.commit()
    flash("Bet placed.", "success")
    return redirect(url_for("prediction.play", code=code))


@bp.route("/<code>/state.json")
@login_required
def state(code):
    game = Game.query.filter_by(code=code, is_enabled=True).first_or_404()
    rnd = _current_round(game)
    remaining = max(0, int((rnd.ends_at - datetime.utcnow()).total_seconds()))
    last = PredictionRound.query.filter_by(game_id=game.id, status="settled") \
        .order_by(PredictionRound.id.desc()).first()
    return jsonify({
        "period": rnd.period_code,
        "remaining": remaining,
        "last_result": {
            "color": last.result_color if last else None,
            "number": last.result_number if last else None,
            "period": last.period_code if last else None,
        },
        "balance": str(wallet_balance(current_user.id)),
    })
