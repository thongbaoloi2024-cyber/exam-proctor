"""Fan-out real-time cho dashboard giam thi - in-process (dict trong RAM cua
1 tien trinh FastAPI), KHONG dung Redis/message broker. Quy mo muc tieu (1
ky thi/1 lop hoc, vai chuc phien dong thoi) khong can ha tang phan tan -
neu sau nay backend chay nhieu worker process thi day la diem can thay bang
Redis pub/sub, nhung chua can o quy mo demo do an.
"""
from __future__ import annotations

from typing import Dict, List

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._dashboard_sockets: Dict[str, List[WebSocket]] = {}
        self._client_sockets: Dict[str, WebSocket] = {}

    async def connect_client(self, session_id: str, websocket: WebSocket) -> bool:
        if session_id in self._client_sockets:
            return False
        self._client_sockets[session_id] = websocket
        try:
            await websocket.accept(
                subprotocol=getattr(websocket.state, "auth_subprotocol", None),
            )
        except Exception:
            self._client_sockets.pop(session_id, None)
            raise
        return True

    def disconnect_client(self, session_id: str, websocket: WebSocket) -> None:
        if self._client_sockets.get(session_id) is websocket:
            self._client_sockets.pop(session_id, None)

    async def connect_dashboard(self, exam_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._dashboard_sockets.setdefault(exam_id, []).append(websocket)

    def disconnect_dashboard(self, exam_id: str, websocket: WebSocket) -> None:
        sockets = self._dashboard_sockets.get(exam_id)
        if sockets and websocket in sockets:
            sockets.remove(websocket)
        if sockets is not None and not sockets:
            self._dashboard_sockets.pop(exam_id, None)

    async def broadcast_to_dashboard(self, exam_id: str, message: dict) -> None:
        for websocket in list(self._dashboard_sockets.get(exam_id, [])):
            try:
                await websocket.send_json(message)
            except Exception:
                self.disconnect_dashboard(exam_id, websocket)


manager = ConnectionManager()
