"""Shared helpers: RNG, ledger, decorators, OTP, fraud checks."""
import secrets
import string
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from functools import wraps
from flask import abort, request, current_app
from flask_login import current_user
from .extensions import db
from .models import (
    WalletTransaction, OtpCode, FraudFlag, AdminLog, User, wallet_balance,
)

_rng = secrets.SystemRandom()


# ---------- RNG ----------
def rand_choice(seq): return _rng.choice(seq)
def rand_int(a, b): return _rng.randint(a, b)
def rand_card():
    suits = ["S", "H", "D", "C"]
    ranks = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K"]
    return f"{_rng.choice(ranks)}{_rng.choice(suits)}"


def card_value(card):
    order = {r: i for i, r in enumerate(
        ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"])}
    return order[card[0]]


def card_color(card):
    return "red" if card[1] in ("H", "D") else "black"


# ---------- IDS / CODES ----------
def gen_referral_code():
    return "".join(_rng.choices(string.ascii_uppercase + string.digits, k=8))


def gen_idem_key(prefix="tx"):
    return f"{prefix}_{uuid.uuid4().hex}"


# ---------- LEDGER ----------
def credit(user_id, amount, *, wallet_type="main", tx_type="deposit",
           reference=None, idem=None, meta=None):
    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValueError("amount must be positive")
    return _post(user_id, amount, wallet_type, tx_type, reference, idem, meta)


def debit(user_id, amount, *, wallet_type="main", tx_type="entry_fee",
          reference=None, idem=None, meta=None, allow_overdraft=False):
    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValueError("amount must be positive")
    bal = wallet_balance(user_id, wallet_type) if wallet_type else wallet_balance(user_id)
    if not allow_overdraft and bal < amount:
        raise ValueError("Insufficient balance")
    return _post(user_id, -amount, wallet_type, tx_type, reference, idem, meta)


def _post(user_id, signed_amount, wallet_type, tx_type, reference, idem, meta):
    if idem:
        existing = WalletTransaction.query.filter_by(idempotency_key=idem).first()
        if existing:
            return existing
    tx = WalletTransaction(
        user_id=user_id, wallet_type=wallet_type, tx_type=tx_type,
        amount=signed_amount, reference=reference,
        idempotency_key=idem or gen_idem_key(tx_type), meta=meta,
    )
    db.session.add(tx)
    db.session.commit()
    return tx


# ---------- OTP ----------
def issue_otp(mobile, purpose="login"):
    code = f"{_rng.randrange(0, 1000000):06d}"
    ttl = current_app.config.get("OTP_TTL_SECONDS", 300)
    db.session.add(OtpCode(mobile=mobile, code=code, purpose=purpose,
                           expires_at=datetime.utcnow() + timedelta(seconds=ttl)))
    db.session.commit()
    if current_app.config.get("OTP_DEV_PRINT", True):
        current_app.logger.warning("[DEV-OTP] %s -> %s (%s)", mobile, code, purpose)
        print(f"\n[DEV-OTP] mobile={mobile} code={code} purpose={purpose}\n")
    # TODO integrate SMS provider (MSG91, Twilio, etc.)
    return code


def verify_otp(mobile, code, purpose="login"):
    rec = OtpCode.query.filter_by(mobile=mobile, code=code, purpose=purpose,
                                  used=False).order_by(OtpCode.id.desc()).first()
    if not rec or rec.expires_at < datetime.utcnow():
        return False
    rec.used = True
    db.session.commit()
    return True


# ---------- DECORATORS ----------
def admin_required(roles=None):
    roles = roles or ("super_admin", "finance_admin", "support_admin")

    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)
            return fn(*a, **kw)
        return wrapper
    return deco


def log_admin(action, target="", detail=""):
    db.session.add(AdminLog(admin_id=current_user.id if current_user.is_authenticated else None,
                            action=action, target=str(target), detail=detail))
    db.session.commit()


# ---------- FRAUD ----------
def flag_fraud(user_id, rule, severity="medium", detail=""):
    db.session.add(FraudFlag(user_id=user_id, rule=rule, severity=severity, detail=detail))
    db.session.commit()


def detect_multi_account(user, ip):
    if not ip:
        return
    same_ip = User.query.filter(User.last_login_ip == ip, User.id != user.id).count()
    if same_ip >= 3:
        flag_fraud(user.id, "multi_account_ip", "high",
                   f"{same_ip} accounts share IP {ip}")


def detect_abnormal_win(user_id, win_amount, entry_amount):
    if Decimal(str(win_amount)) >= Decimal(str(entry_amount)) * 50:
        flag_fraud(user_id, "abnormal_win", "high",
                   f"win {win_amount} on entry {entry_amount}")


def client_ip():
    return (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip()
