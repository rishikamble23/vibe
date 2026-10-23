"""
Unit tests for Phase 7 API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta

from app.main import app
from app.clock import SimClock, set_clock


client = TestClient(app)


class TestAPI:

    def test_health(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_create_batch(self):
        clock = SimClock(datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc))
        set_clock(clock)

        payload = {
            "donor_id": 1,
            "category": "cooked_meal",
            "qty": 50,
            "unit": "portion",
            "cooked_at": "2024-01-01T08:00:00Z",
        }

        response = client.post("/batches", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert "batch" in data
        assert "lots" in data
        assert data["batch"]["qty_portions"] == 50
        assert len(data["lots"]) > 0

    def test_snapshot_and_reset(self):
        # Reset first
        client.post("/admin/reset")
        
        resp = client.get("/state/snapshot")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["batches"]) == 0
