from decimal import Decimal
from flask import Blueprint, render_template, flash
from flask_login import login_required, current_user
from ..extensions import db
from ..models import User, Referral
from ..utils import credit

bp = Blueprint("referrals", __name__, template_folder="../templates/referrals")

REFERRAL_BONUS = Decimal("50")


@bp.route("/")
@login_required
def index():
    rows = Referral.query.filter_by(referrer_id=current_user.id).all()
    refs = []
    for r in rows:
        refs.append((User.query.get(r.referee_id), r.bonus_paid))
    return render_template("referrals/index.html",
                           code=current_user.referral_code, refs=refs)


@bp.route("/claim")
@login_required
def claim():
    """Pay one-time referral bonus once a referee verifies."""
    paid = 0
    referees = User.query.filter_by(referred_by_id=current_user.id,
                                    is_verified=True).all()
    for ref in referees:
        existing = Referral.query.filter_by(referrer_id=current_user.id,
                                            referee_id=ref.id).first()
        if existing and existing.bonus_paid > 0:
            continue
        if not existing:
            existing = Referral(referrer_id=current_user.id, referee_id=ref.id)
            db.session.add(existing)
        credit(current_user.id, REFERRAL_BONUS, wallet_type="bonus",
               tx_type="referral_bonus", reference=f"ref:{ref.id}",
               idem=f"ref_bonus_{current_user.id}_{ref.id}")
        existing.bonus_paid = REFERRAL_BONUS
        paid += 1
    db.session.commit()
    flash(f"Claimed bonus for {paid} referral(s).", "success")
    from flask import redirect, url_for
    return redirect(url_for("referrals.index"))
