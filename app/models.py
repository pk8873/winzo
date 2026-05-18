"""All SQLAlchemy models + admin bootstrap."""
from datetime import datetime, timedelta
from decimal import Decimal
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from sqlalchemy import func
from .extensions import db


# ---------- USERS ----------
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    email = db.Column(db.String(190), unique=True, index=True)
    mobile = db.Column(db.String(20), unique=True, index=True)
    password_hash = db.Column(db.String(255))
    role = db.Column(db.String(32), default="user")  # user, support_admin, finance_admin, super_admin
    is_blocked = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    referral_code = db.Column(db.String(16), unique=True, index=True)
    referred_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    last_login_ip = db.Column(db.String(64))
    failed_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw): self.password_hash = generate_password_hash(pw)
    def check_password(self, pw): return check_password_hash(self.password_hash or "", pw)
    def is_admin(self): return self.role in ("super_admin", "finance_admin", "support_admin")
    def is_super(self): return self.role == "super_admin"


# ---------- WALLET LEDGER ----------
class WalletTransaction(db.Model):
    __tablename__ = "wallet_transactions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True, nullable=False)
    wallet_type = db.Column(db.String(16), nullable=False)  # main, winning, bonus
    tx_type = db.Column(db.String(32), nullable=False)      # deposit, withdraw, entry_fee, winnings, referral_bonus, admin_adjust
    amount = db.Column(db.Numeric(14, 2), nullable=False)   # signed
    reference = db.Column(db.String(120), index=True)       # external ref (razorpay payment id, etc.)
    idempotency_key = db.Column(db.String(120), unique=True, index=True)
    meta = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


# ---------- DEPOSITS / WITHDRAWALS ----------
class Deposit(db.Model):
    __tablename__ = "deposits"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    provider = db.Column(db.String(32), default="razorpay")
    order_id = db.Column(db.String(120), index=True)
    payment_id = db.Column(db.String(120), index=True)
    status = db.Column(db.String(20), default="pending")  # pending, success, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Withdrawal(db.Model):
    __tablename__ = "withdrawals"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    method = db.Column(db.String(20), default="upi")  # upi, bank
    upi_id = db.Column(db.String(120))
    bank_account = db.Column(db.String(60))
    ifsc = db.Column(db.String(20))
    account_holder = db.Column(db.String(120))
    status = db.Column(db.String(20), default="pending")  # pending, approved, rejected, paid
    admin_note = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    decided_at = db.Column(db.DateTime)


# ---------- GAMES ----------
class Game(db.Model):
    __tablename__ = "games"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(40))  # prediction, card, flash
    description = db.Column(db.String(255))
    is_enabled = db.Column(db.Boolean, default=True)
    rtp = db.Column(db.Float, default=0.90)
    min_entry = db.Column(db.Numeric(10, 2), default=10)
    max_entry = db.Column(db.Numeric(10, 2), default=10000)
    round_seconds = db.Column(db.Integer, default=60)


class PredictionRound(db.Model):
    __tablename__ = "prediction_rounds"
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey("games.id"), index=True)
    period_code = db.Column(db.String(40), unique=True, index=True)
    starts_at = db.Column(db.DateTime, default=datetime.utcnow)
    ends_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="open")  # open, locked, settled
    result_color = db.Column(db.String(16))
    result_number = db.Column(db.Integer)
    settled_at = db.Column(db.DateTime)


class CardRound(db.Model):
    __tablename__ = "card_rounds"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    game_id = db.Column(db.Integer, db.ForeignKey("games.id"))
    bet_type = db.Column(db.String(32))   # red_black, suit, higher_lower
    choice = db.Column(db.String(32))
    amount = db.Column(db.Numeric(10, 2))
    drawn_card = db.Column(db.String(8))
    prev_card = db.Column(db.String(8))
    is_win = db.Column(db.Boolean, default=False)
    payout = db.Column(db.Numeric(12, 2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class GameEntry(db.Model):
    __tablename__ = "game_entries"
    id = db.Column(db.Integer, primary_key=True)
    round_id = db.Column(db.Integer, db.ForeignKey("prediction_rounds.id"), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    pick_type = db.Column(db.String(16))    # color, number
    pick_value = db.Column(db.String(16))
    amount = db.Column(db.Numeric(10, 2))
    is_win = db.Column(db.Boolean)
    payout = db.Column(db.Numeric(12, 2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------- REFERRALS ----------
class Referral(db.Model):
    __tablename__ = "referrals"
    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    referee_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    bonus_paid = db.Column(db.Numeric(10, 2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------- NOTIFICATIONS ----------
class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)  # null = broadcast
    title = db.Column(db.String(160))
    body = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------- ADMIN AUDIT / FRAUD ----------
class AdminLog(db.Model):
    __tablename__ = "admin_logs"
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(80))
    target = db.Column(db.String(120))
    detail = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FraudFlag(db.Model):
    __tablename__ = "fraud_flags"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    rule = db.Column(db.String(80))
    severity = db.Column(db.String(16), default="medium")  # low, medium, high
    detail = db.Column(db.Text)
    resolved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class OtpCode(db.Model):
    __tablename__ = "otp_codes"
    id = db.Column(db.Integer, primary_key=True)
    mobile = db.Column(db.String(20), index=True)
    code = db.Column(db.String(8))
    purpose = db.Column(db.String(32))   # register, login, reset
    expires_at = db.Column(db.DateTime)
    used = db.Column(db.Boolean, default=False)


# ---------- WALLET HELPERS ----------
def wallet_balance(user_id, wallet_type=None):
    q = db.session.query(func.coalesce(func.sum(WalletTransaction.amount), 0)) \
        .filter(WalletTransaction.user_id == user_id)
    if wallet_type:
        q = q.filter(WalletTransaction.wallet_type == wallet_type)
    return Decimal(q.scalar() or 0)


def total_balance(user_id):
    return wallet_balance(user_id)


# ---------- BOOTSTRAP ----------
def bootstrap_admin(app):
    email = app.config.get("ADMIN_EMAIL")
    mobile = app.config.get("ADMIN_MOBILE")
    if not email:
        return
    u = User.query.filter_by(email=email).first()
    if not u:
        u = User(name="Super Admin", email=email, mobile=mobile,
                 role="super_admin", is_verified=True,
                 referral_code="ADMIN001")
        u.set_password(app.config.get("ADMIN_PASSWORD"))
        db.session.add(u)
        db.session.commit()
        app.logger.info("Bootstrapped admin: %s", email)
    # Seed games
    defaults = [
        dict(code="color_pred", name="Color Prediction", category="prediction",
             description="Pick Red, Green or Violet", round_seconds=60),
        dict(code="number_pred", name="Number Prediction", category="prediction",
             description="Pick a number 0-9", round_seconds=60),
        dict(code="card_rb", name="Red or Black", category="card",
             description="Guess the color of the next card", round_seconds=0),
        dict(code="card_suit", name="Card Suit", category="card",
             description="Guess the suit (♠ ♥ ♦ ♣)", round_seconds=0),
        dict(code="card_hl", name="Higher or Lower", category="card",
             description="Will the next card be higher or lower?", round_seconds=0),
        dict(code="flash_cards", name="Flash Cards", category="flash",
             description="Fast 30s card rounds", round_seconds=30),
    ]
    for d in defaults:
        if not Game.query.filter_by(code=d["code"]).first():
            db.session.add(Game(rtp=app.config.get("DEFAULT_RTP", 0.9), **d))
    db.session.commit()
