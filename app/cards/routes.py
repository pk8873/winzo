"""Card games: Red/Black, Suit, Higher/Lower, Flash Cards (instant)."""
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Game, CardRound, wallet_balance
from ..utils import (rand_card, card_value, card_color, credit, debit,
                     gen_idem_key, detect_abnormal_win, rand_int)

bp = Blueprint("cards", __name__, template_folder="../templates/cards")

SUITS = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}
PAYOUT = {"red_black": Decimal("2"), "suit": Decimal("4"), "higher_lower": Decimal("2")}


@bp.route("/<code>")
@login_required
def play(code):
    game = Game.query.filter_by(code=code, is_enabled=True).first_or_404()
    last = CardRound.query.filter_by(user_id=current_user.id, game_id=game.id) \
        .order_by(CardRound.id.desc()).first()
    history = CardRound.query.filter_by(user_id=current_user.id, game_id=game.id) \
        .order_by(CardRound.id.desc()).limit(10).all()
    return render_template("cards/play.html", game=game, last=last, history=history,
                           suits=SUITS, balance=wallet_balance(current_user.id))


@bp.route("/<code>/draw", methods=["POST"])
@login_required
def draw(code):
    game = Game.query.filter_by(code=code, is_enabled=True).first_or_404()
    try:
        amount = Decimal(request.form.get("amount", "0"))
    except Exception:
        amount = Decimal("0")
    if amount < game.min_entry or amount > game.max_entry:
        flash("Bet outside allowed range.", "danger")
        return redirect(url_for("cards.play", code=code))
    bet_type = request.form.get("bet_type", "red_black")
    choice = request.form.get("choice", "")
    prev = CardRound.query.filter_by(user_id=current_user.id, game_id=game.id) \
        .order_by(CardRound.id.desc()).first()
    prev_card = prev.drawn_card if prev else rand_card()
    try:
        debit(current_user.id, amount, wallet_type="main", tx_type="entry_fee",
              reference=f"card:{game.code}", idem=gen_idem_key("card"))
    except ValueError as e:
        flash(str(e), "danger"); return redirect(url_for("cards.play", code=code))
    drawn = rand_card()
    # RTP-biased: small chance to re-roll against the user
    if rand_int(1, 100) > int((game.rtp or 0.9) * 100):
        for _ in range(3):
            cand = rand_card()
            if not _is_win(bet_type, choice, cand, prev_card):
                drawn = cand; break
    win = _is_win(bet_type, choice, drawn, prev_card)
    payout = amount * PAYOUT.get(bet_type, Decimal("2")) if win else Decimal("0")
    cr = CardRound(user_id=current_user.id, game_id=game.id, bet_type=bet_type,
                   choice=choice, amount=amount, drawn_card=drawn,
                   prev_card=prev_card, is_win=win, payout=payout)
    db.session.add(cr); db.session.commit()
    if win:
        credit(current_user.id, payout, wallet_type="winning", tx_type="winnings",
               reference=f"card:{cr.id}", idem=f"cardwin_{cr.id}")
        detect_abnormal_win(current_user.id, payout, amount)
    flash(("You won ₹%s!" % payout) if win else "No luck this time.",
          "success" if win else "warning")
    return redirect(url_for("cards.play", code=code))


def _is_win(bet_type, choice, card, prev_card):
    if bet_type == "red_black":
        return card_color(card) == choice
    if bet_type == "suit":
        return card[1] == choice
    if bet_type == "higher_lower":
        nv, pv = card_value(card), card_value(prev_card)
        if nv == pv:
            return False
        return (choice == "higher" and nv > pv) or (choice == "lower" and nv < pv)
    return False
