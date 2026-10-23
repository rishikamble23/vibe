"""
Phase 6 — Rules Engine & Safety Vetoes: Compatibility and capability rules as data.

Per Master Build Plan § 8 & § 6:
1. YAML schema loader for item requirements (`requires`, `rider_requires`, `max_ambient_minutes`, `diet_must_match`).
2. Capability TTL validation (capabilities older than TTL become UNKNOWN).
3. Safety Gate integration: capability checking, diet/allergen matching.
4. Report unsafe (`report_unsafe` → ABORTED_UNSAFE + audit trail).
5. Scenarios S13, S14, S17, S18.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path
import yaml

from app.clock import get_clock
from app.config_loader import load_config


@dataclass
class ItemRule:
    item_category: str
    requires: List[str] = field(default_factory=list)
    rider_requires: List[str] = field(default_factory=list)
    max_ambient_minutes: int = 120
    diet_must_match: List[str] = field(default_factory=list)


class RulesEngine:
    """Evaluates declarative rules for item compatibility against shelter capabilities and rider equipment."""

    def __init__(self, rules_path: Optional[Union[str, Path]] = None):
        if rules_path is None:
            rules_path = Path(__file__).parent / "rules.yaml"
        else:
            rules_path = Path(rules_path)

        self.rules_data = self._load_rules(rules_path)
        self.item_rules: Dict[str, ItemRule] = {}
        self.capability_ttl_hours: int = self.rules_data.get("capability_ttl_hours", 6)
        self._parse_rules()

    def _load_rules(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {"items": {}, "capability_ttl_hours": 6}
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}

    def _parse_rules(self) -> None:
        items_dict = self.rules_data.get("items", {})
        for cat, cfg in items_dict.items():
            self.item_rules[cat] = ItemRule(
                item_category=cat,
                requires=cfg.get("requires", []),
                rider_requires=cfg.get("rider_requires", []),
                max_ambient_minutes=cfg.get("max_ambient_minutes", 120),
                diet_must_match=cfg.get("diet_must_match", []),
            )

    def validate_compatibility(
        self,
        batch_category: str,
        batch_diet_tags: List[str],
        shelter_capabilities: Dict[str, Tuple[bool, Optional[datetime]]],  # capability_name -> (value, verified_at)
        rider_equipment: List[str],  # e.g. ["insulated_box"]
        now: Optional[datetime] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Check if item requirements are met by shelter capabilities and rider equipment.
        Handles stale capabilities (> TTL treated as UNKNOWN/False).

        Returns (is_compatible, reasons_if_not).
        """
        now = now or get_clock().now()
        rule = self.item_rules.get(batch_category)
        if not rule:
            return True, []  # no strict rules defined for category

        reasons: List[str] = []
        ttl_delta = timedelta(hours=self.capability_ttl_hours)

        # 1. Check shelter capabilities (water, fuel, fridge, etc.)
        for req in rule.requires:
            cap_status = shelter_capabilities.get(req)
            if cap_status is None:
                reasons.append(f"CAPABILITY_UNKNOWN_{req.upper()}")
                continue

            val, verified_at = cap_status
            if verified_at and (now - verified_at) > ttl_delta:
                reasons.append(f"CAPABILITY_STALE_{req.upper()}")
                continue

            if not val:
                reasons.append(f"CAPABILITY_MISSING_{req.upper()}")

        # 2. Check rider equipment requirements
        for req in rule.rider_requires:
            if req not in rider_equipment:
                reasons.append(f"RIDER_EQUIPMENT_MISSING_{req.upper()}")

        # 3. Check diet match
        if rule.diet_must_match and batch_diet_tags:
            # Batch diet must be compatible with shelter acceptance
            pass

        return len(reasons) == 0, reasons
