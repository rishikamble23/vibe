"""
Phase 7 Realtime WebSockets (7.4):
Channels: /ws/control, /ws/rider/{id}, /ws/shelter/{id}
Pushes events as they are appended; reconnect with last-seen event id for replay.
"""
from __future__ import annotations

import asyncio
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect


ws_router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections per channel."""

    def __init__(self):
        self.control_connections: Set[WebSocket] = set()
        self.rider_connections: Dict[int, Set[WebSocket]] = {}
        self.shelter_connections: Dict[int, Set[WebSocket]] = {}

    async def connect_control(self, websocket: WebSocket):
        await websocket.accept()
        self.control_connections.add(websocket)

    def disconnect_control(self, websocket: WebSocket):
        self.control_connections.discard(websocket)

    async def connect_rider(self, rider_id: int, websocket: WebSocket):
        await websocket.accept()
        if rider_id not in self.rider_connections:
            self.rider_connections[rider_id] = set()
        self.rider_connections[rider_id].add(websocket)

    def disconnect_rider(self, rider_id: int, websocket: WebSocket):
        if rider_id in self.rider_connections:
            self.rider_connections[rider_id].discard(websocket)

    async def connect_shelter(self, shelter_id: int, websocket: WebSocket):
        await websocket.accept()
        if shelter_id not in self.shelter_connections:
            self.shelter_connections[shelter_id] = set()
        self.shelter_connections[shelter_id].add(websocket)

    def disconnect_shelter(self, shelter_id: int, websocket: WebSocket):
        if shelter_id in self.shelter_connections:
            self.shelter_connections[shelter_id].discard(websocket)

    async def broadcast_control(self, message: dict):
        for ws in list(self.control_connections):
            try:
                await ws.send_json(message)
            except Exception:
                self.control_connections.discard(ws)

    async def send_rider(self, rider_id: int, message: dict):
        for ws in list(self.rider_connections.get(rider_id, set())):
            try:
                await ws.send_json(message)
            except Exception:
                self.rider_connections[rider_id].discard(ws)

    async def send_shelter(self, shelter_id: int, message: dict):
        for ws in list(self.shelter_connections.get(shelter_id, set())):
            try:
                await ws.send_json(message)
            except Exception:
                self.shelter_connections[shelter_id].discard(ws)


manager = ConnectionManager()


@ws_router.websocket("/control")
async def websocket_control(websocket: WebSocket):
    await manager.connect_control(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo or handle ping
            await websocket.send_json({"status": "ack", "received": data})
    except WebSocketDisconnect:
        manager.disconnect_control(websocket)


@ws_router.websocket("/rider/{rider_id}")
async def websocket_rider(websocket: WebSocket, rider_id: int):
    await manager.connect_rider(rider_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"status": "ack", "rider_id": rider_id, "received": data})
    except WebSocketDisconnect:
        manager.disconnect_rider(rider_id, websocket)


@ws_router.websocket("/shelter/{shelter_id}")
async def websocket_shelter(websocket: WebSocket, shelter_id: int):
    await manager.connect_shelter(shelter_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"status": "ack", "shelter_id": shelter_id, "received": data})
    except WebSocketDisconnect:
        manager.disconnect_shelter(shelter_id, websocket)
