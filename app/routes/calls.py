from collections import defaultdict
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.database import SessionLocal
from app.models import User
from app.security import decode_access_token


router = APIRouter(tags=["Calls"])


# Users currently connected to the call WebSocket
connections: dict[int, set[WebSocket]] = defaultdict(set)

# Temporarily save WebRTC signals if the other user
# has not opened the call page yet
pending_signals: dict[int, list[dict]] = defaultdict(list)

lock = asyncio.Lock()


async def send_to(user_id: int, payload: dict):
    """
    Send WebRTC offer / answer / ICE to another user.
    If that user isn't connected yet, save it temporarily.
    """

    dead_connections = []
    delivered = False

    sockets = list(connections.get(user_id, set()))

    for ws in sockets:
        try:
            await ws.send_json(payload)
            delivered = True

        except Exception:
            dead_connections.append(ws)

    # Remove broken WebSocket connections
    if dead_connections:
        async with lock:
            for ws in dead_connections:
                connections[user_id].discard(ws)

    # User is not connected yet
    if not delivered:
        async with lock:
            pending_signals[user_id].append(payload)

            # Don't let the queue grow forever
            if len(pending_signals[user_id]) > 100:
                pending_signals[user_id] = pending_signals[user_id][-100:]

        print(
            f"CALL SIGNAL QUEUED -> user={user_id}, "
            f"type={payload.get('type')}"
        )

    else:
        print(
            f"CALL SIGNAL SENT -> user={user_id}, "
            f"type={payload.get('type')}"
        )


@router.websocket("/ws/calls")
async def call_socket(websocket: WebSocket, token: str):

    # ------------------------------
    # CHECK LOGIN TOKEN
    # ------------------------------

    try:
        user_id = decode_access_token(token)

    except ValueError:
        await websocket.close(code=4401)
        return


    db = SessionLocal()

    try:

        # ------------------------------
        # FIND LOGGED-IN USER
        # ------------------------------

        user = db.get(User, user_id)

        if not user:
            await websocket.close(code=4401)
            return


        # ------------------------------
        # ACCEPT WEBSOCKET
        # ------------------------------

        await websocket.accept()

        async with lock:

            connections[user_id].add(websocket)

            # Get signals that came before user connected
            queued_messages = pending_signals.pop(user_id, [])


        print(f"CALL WS CONNECTED -> USER {user_id}")


        # Tell frontend connection is ready
        await websocket.send_json({
            "type": "ready",
            "user_id": user_id
        })


        # ------------------------------
        # SEND SAVED SIGNALS
        # ------------------------------

        for message in queued_messages:

            try:
                await websocket.send_json(message)

                print(
                    f"QUEUED SIGNAL DELIVERED -> "
                    f"user={user_id}, "
                    f"type={message.get('type')}"
                )

            except Exception as error:
                print("QUEUED SIGNAL ERROR:", error)


        # ------------------------------
        # LISTEN FOR CALL MESSAGES
        # ------------------------------

        while True:

            data = await websocket.receive_json()

            signal_type = data.get("type")

            print(
                f"CALL SIGNAL RECEIVED <- "
                f"user={user_id}, "
                f"type={signal_type}"
            )


            # Person receiving this WebRTC message
            target = data.get("target_user_id")

            try:
                target = int(target or 0)

            except (TypeError, ValueError):
                target = 0


            if not target:
                print("CALL SIGNAL HAS NO TARGET")
                continue


            # Add caller information
            payload = {
                **data,
                "from_user_id": user_id,
                "from_username": user.username
            }


            # Send offer / answer / ICE
            await send_to(
                target,
                payload
            )


    except WebSocketDisconnect:

        print(
            f"CALL WS DISCONNECTED -> USER {user_id}"
        )


    except Exception as error:

        print(
            f"CALL WEBSOCKET ERROR -> USER {user_id}:",
            error
        )


    finally:

        async with lock:

            connections[user_id].discard(websocket)

            if not connections[user_id]:
                connections.pop(user_id, None)

        db.close()