"""
Phase 4 — Planner: Candidate generation, scoring, greedy EDF, multi-drop, and splitting.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.clock import get_clock
from app.config_loader import get_config, get_scoring_weights
from app.eta import get_eta_service
from app.safety_gate import SafetyGate, get_safety_gate, SafetyReason


@dataclass
class CandidateTriple:
    rider: Any
    lot: Any
    shelter: Any
    batch: Any
    p90_rider_to_donor: int
    p90_donor_to_shelter: int
    slack_minutes: int
    score: float = 0.0
    reason_str: str = ""


@dataclass
class PlanAssignment:
    lot_id: int
    rider_id: int
    shelter_id: int
    qty: int
    score: float
    explanation: str


@dataclass
class PlannerResult:
    version: int
    assignments: List[PlanAssignment]
    unplaced_lots: List[int]
    runtime_ms: float
    explanation: str


def score_candidate(
    triple: CandidateTriple,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    if weights is None:
        weights = get_scoring_weights()

    urgency_w = weights.get("urgency_weight", 1.0)
    detour_w = weights.get("detour_weight", 0.5)
    late_w = weights.get("late_probability_weight", 2.0)
    reliability_w = weights.get("reliability_weight", 1.5)

    lot_qty = getattr(triple.lot, "qty", 10)
    reliability = getattr(triple.rider, "reliability_score", 0.8)

    shelter_need = max(1, getattr(triple.shelter, "need", 50))
    urgency = min(2.0, shelter_need / 50.0)

    total_time = triple.p90_rider_to_donor + triple.p90_donor_to_shelter
    detour_penalty = total_time * detour_w

    slack = triple.slack_minutes
    late_prob = max(0.0, 1.0 - (slack / 60.0))
    late_penalty = late_prob * 50.0 * late_w

    reliability_bonus = reliability * 20.0 * reliability_w

    score = (lot_qty * urgency * urgency_w) - detour_penalty - late_penalty + reliability_bonus
    return score


class GreedyEDFPlanner:
    """Greedy EDF Planner with multi-drop and lot splitting."""

    def __init__(
        self,
        safety_gate: Optional[SafetyGate] = None,
        eta_service: Optional[Any] = None,
    ):
        self.safety_gate = safety_gate or get_safety_gate()
        self.eta_service = eta_service or get_eta_service()

    def plan(
        self,
        version: int,
        lots: List[Any],
        riders: List[Any],
        shelters: List[Any],
        batches_map: Dict[int, Any],
        now: Optional[datetime] = None,
    ) -> PlannerResult:
        t_start = time.time()
        now = now or get_clock().now()

        active_lots = [l for l in lots if getattr(l, "status", "unassigned") == "unassigned"]
        active_lots.sort(key=lambda l: getattr(l, "deliver_by", now))

        rider_loads = {r.id: 0 for r in riders}
        rider_map = {r.id: r for r in riders}
        shelter_holds = {s.id: (s.need - s.received - s.committed) for s in shelters}

        assignments: List[PlanAssignment] = []
        lot_remaining = {l.id: l.qty for l in active_lots}
        fully_assigned_lots: set = set()

        for lot in active_lots:
            if lot.id in fully_assigned_lots:
                continue

            batch = batches_map.get(lot.batch_id)
            if not batch:
                continue

            while lot_remaining[lot.id] > 0:
                best_cand = None
                best_score = -999999.0

                for rider in riders:
                    current_load = rider_loads[rider.id]
                    remaining_cap = rider.vehicle_capacity - current_load
                    if remaining_cap <= 0:
                        continue

                    for shelter in shelters:
                        avail = shelter_holds.get(shelter.id, 0)
                        if avail <= 0:
                            continue

                        res = self.safety_gate.is_safe(lot, rider, shelter, batch, now=now)
                        if res.ok:
                            triple = CandidateTriple(
                                rider=rider,
                                lot=lot,
                                shelter=shelter,
                                batch=batch,
                                p90_rider_to_donor=res.details.get("rider_to_donor_p90", 10),
                                p90_donor_to_shelter=res.details.get("donor_to_shelter_p90", 15),
                                slack_minutes=res.slack_minutes,
                            )
                            score = score_candidate(triple)
                            if score > best_score:
                                best_score = score
                                best_cand = (rider, shelter, triple, remaining_cap)

                if not best_cand:
                    break

                rider, shelter, triple, remaining_cap = best_cand
                avail = shelter_holds[shelter.id]
                take_qty = min(lot_remaining[lot.id], avail, remaining_cap)

                if take_qty <= 0:
                    break

                shelter_holds[shelter.id] -= take_qty
                lot_remaining[lot.id] -= take_qty
                rider_loads[rider.id] += take_qty

                assignments.append(
                    PlanAssignment(
                        lot_id=lot.id,
                        rider_id=rider.id,
                        shelter_id=shelter.id,
                        qty=take_qty,
                        score=best_score,
                        explanation=f"chosen: slack {triple.slack_minutes} min, reliability {rider.reliability_score}",
                    )
                )

                if lot_remaining[lot.id] <= 0:
                    fully_assigned_lots.add(lot.id)
                    break

        unplaced = [l.id for l in active_lots if lot_remaining.get(l.id, l.qty) > 0 and l.id not in fully_assigned_lots]
        runtime = (time.time() - t_start) * 1000.0

        return PlannerResult(
            version=version,
            assignments=assignments,
            unplaced_lots=unplaced,
            runtime_ms=runtime,
            explanation=f"Greedy EDF planner completed in {runtime:.1f}ms: {len(assignments)} assignments, {len(unplaced)} unplaced.",
        )
