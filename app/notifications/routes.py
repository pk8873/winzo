from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Notification

bp = Blueprint("notifications", __name__, template_folder="../templates/notifications")


@bp.route("/")
@login_required
def inbox():
    rows = Notification.query.filter(
        (Notification.user_id == current_user.id) | (Notification.user_id == None)  # noqa
    ).order_by(Notification.id.desc()).limit(100).all()
    return render_template("notifications/inbox.html", rows=rows)


@bp.route("/<int:nid>/read", methods=["POST"])
@login_required
def mark_read(nid):
    n = Notification.query.get_or_404(nid)
    if n.user_id == current_user.id:
        n.is_read = True; db.session.commit()
    return redirect(url_for("notifications.inbox"))
