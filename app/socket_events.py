"""SocketIO events: live timers & broadcasts."""
from flask_socketio import emit, join_room
from .extensions import socketio


@socketio.on("connect")
def on_connect():
    emit("server_hello", {"msg": "connected"})


@socketio.on("join_round")
def on_join(data):
    room = f"round_{data.get('round_id')}"
    join_room(room)
    emit("joined", {"room": room})


def broadcast_timer(round_id, remaining):
    socketio.emit("timer_tick", {"round_id": round_id, "remaining": remaining},
                  to=f"round_{round_id}")


def broadcast_result(round_id, payload):
    socketio.emit("round_result", payload, to=f"round_{round_id}")


def broadcast_wallet(user_id, balance):
    socketio.emit("wallet_update", {"balance": str(balance)}, to=f"user_{user_id}")
