"""Fan-out real-time cho dashboard giam thi - in-process (dict trong RAM cua
1 tien trinh FastAPI), KHONG dung Redis/message broker. Quy mo muc tieu (1
ky thi/1 lop hoc, vai chuc phien dong thoi) khong can ha tang phan tan -
neu sau nay backend chay nhieu worker process thi day la diem can thay bang
Redis pub/sub, nhung chua can o quy mo demo do an.
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
from typing import Dict, List

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._dashboard_sockets: Dict[str, List[WebSocket]] = {}
        self._client_sockets: Dict[str, WebSocket] = {}
        self._redis_url = os.environ.get("REDIS_URL", "").strip()
        self._redis = None
        self._redis_pubsub = None
        self._subscriber_task = None
        self._client_leases: Dict[str, str] = {}

    def _redis_client(self):
        if not self._redis_url:
            return None
        if self._redis is None:
            try:
                import redis.asyncio as redis
            except ImportError as exc:
                raise RuntimeError("REDIS_URL da dat nhung chua cai package redis") from exc
            self._redis = redis.Redis.from_url(self._redis_url, decode_responses=True)
        return self._redis

    async def _release_client_lease(self, session_id: str) -> None:
        client = self._redis_client()
        owner = self._client_leases.pop(session_id, None)
        if client is None or owner is None:
            return
        await client.eval(
            "if redis.call('get', KEYS[1]) == ARGV[1] then "
            "return redis.call('del', KEYS[1]) else return 0 end",
            1,
            f"datt:client:{session_id}",
            owner,
        )

    async def _ensure_subscriber(self) -> None:
        client = self._redis_client()
        if client is None or self._subscriber_task is not None:
            return
        self._redis_pubsub = client.pubsub()
        await self._redis_pubsub.psubscribe("datt:dashboard:*")
        self._subscriber_task = asyncio.create_task(self._listen_dashboard_messages())

    async def _listen_dashboard_messages(self) -> None:
        assert self._redis_pubsub is not None
        async for item in self._redis_pubsub.listen():
            if item.get("type") != "pmessage":
                continue
            channel = str(item.get("channel", ""))
            exam_id = channel.removeprefix("datt:dashboard:")
            try:
                message = json.loads(item["data"])
            except (TypeError, ValueError):
                continue
            await self._broadcast_local(exam_id, message)

    async def connect_client(self, session_id: str, websocket: WebSocket) -> bool:
        if session_id in self._client_sockets:
            return False
        client = self._redis_client()
        if client is not None:
            owner = secrets.token_urlsafe(18)
            acquired = await client.set(
                f"datt:client:{session_id}", owner, nx=True, ex=120,
            )
            if not acquired:
                return False
            self._client_leases[session_id] = owner
        self._client_sockets[session_id] = websocket
        try:
            await websocket.accept(
                subprotocol=getattr(websocket.state, "auth_subprotocol", None),
            )
        except Exception:
            self._client_sockets.pop(session_id, None)
            await self._release_client_lease(session_id)
            raise
        return True

    async def touch_client(self, session_id: str) -> None:
        client = self._redis_client()
        owner = self._client_leases.get(session_id)
        if client is None or owner is None:
            return
        await client.eval(
            "if redis.call('get', KEYS[1]) == ARGV[1] then "
            "return redis.call('expire', KEYS[1], ARGV[2]) else return 0 end",
            1,
            f"datt:client:{session_id}",
            owner,
            120,
        )

    async def disconnect_client(self, session_id: str, websocket: WebSocket) -> None:
        if self._client_sockets.get(session_id) is websocket:
            self._client_sockets.pop(session_id, None)
            await self._release_client_lease(session_id)

    async def force_close_client(self, session_id: str) -> None:
        websocket = self._client_sockets.pop(session_id, None)
        await self._release_client_lease(session_id)
        if websocket is None:
            return
        try:
            await websocket.send_json({
                "type": "session_ended",
                "data": {"reason": "ended_by_proctor"},
            })
            await websocket.close(code=4410, reason="ended by proctor")
        except Exception:
            pass

    async def connect_dashboard(self, exam_id: str, websocket: WebSocket) -> None:
        await self._ensure_subscriber()
        await websocket.accept()
        self._dashboard_sockets.setdefault(exam_id, []).append(websocket)

    def disconnect_dashboard(self, exam_id: str, websocket: WebSocket) -> None:
        sockets = self._dashboard_sockets.get(exam_id)
        if sockets and websocket in sockets:
            sockets.remove(websocket)
        if sockets is not None and not sockets:
            self._dashboard_sockets.pop(exam_id, None)

    async def _broadcast_local(self, exam_id: str, message: dict) -> None:
        for websocket in list(self._dashboard_sockets.get(exam_id, [])):
            try:
                await websocket.send_json(message)
            except Exception:
                self.disconnect_dashboard(exam_id, websocket)

    async def broadcast_to_dashboard(self, exam_id: str, message: dict) -> None:
        client = self._redis_client()
        if client is None:
            await self._broadcast_local(exam_id, message)
            return
        await client.publish(
            f"datt:dashboard:{exam_id}",
            json.dumps(message, ensure_ascii=False),
        )


manager = ConnectionManager()
