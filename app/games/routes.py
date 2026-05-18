from flask import Blueprint, render_template
from flask_login import login_required
from ..models import Game, GameEntry, CardRound, User, wallet_balance
from sqlalchemy import desc, func
from ..extensions import db

bp = Blueprint("games", __name__, template_folder="../templates/games")


@bp.route("/")
@login_required
def lobby():
    games = Game.query.filter_by(is_enabled=True).all()
    return render_template("games/lobby.html", games=games)


@bp.route("/leaderboard")
@login_required
def leaderboard():
    # top winners by sum of payouts (prediction + card)
    pred = db.session.query(GameEntry.user_id, func.sum(GameEntry.payout).label("p")) \
        .group_by(GameEntry.user_id).subquery()
    card = db.session.query(CardRound.user_id, func.sum(CardRound.payout).label("p")) \
        .group_by(CardRound.user_id).subquery()
    rows = db.session.query(User,
                            func.coalesce(pred.c.p, 0) + func.coalesce(card.c.p, 0).label("total")) \
        .outerjoin(pred, pred.c.user_id == User.id) \
        .outerjoin(card, card.c.user_id == User.id) \
        .order_by(desc("total")).limit(20).all()
    return render_template("games/leaderboard.html", rows=rows)
