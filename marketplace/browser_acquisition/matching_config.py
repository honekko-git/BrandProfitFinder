"""Load deterministic comparable-matching weights, thresholds, and hard-reject flags."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "matching_config.json"


@dataclass(frozen=True, slots=True)
class MatchingWeights:
    model_number: int
    brand: int
    category: int
    category_related: int
    material: int
    color: int
    hardware: int
    title_similarity: int
    title_token: int
    model_family: int
    condition: int


@dataclass(frozen=True, slots=True)
class MatchingThresholds:
    accept_threshold: int
    near_miss_threshold: int


@dataclass(frozen=True, slots=True)
class MatchingHardReject:
    different_model_number: bool
    category_conflict: bool
    material_conflict: bool


@dataclass(frozen=True, slots=True)
class MatchingConfig:
    weights: MatchingWeights
    thresholds: MatchingThresholds
    hard_reject: MatchingHardReject


def load_matching_config(path: Path | str | None = None) -> MatchingConfig:
    """Load matching configuration from JSON. Values mirror prior in-code constants."""
    config_path = Path(path) if path is not None else _DEFAULT_PATH
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    weights = payload["weights"]
    thresholds = payload.get("thresholds") or {}
    hard_reject = payload["hard_reject"]
    return MatchingConfig(
        weights=MatchingWeights(
            model_number=int(weights["model_number"]),
            brand=int(weights["brand"]),
            category=int(weights["category"]),
            category_related=int(weights["category_related"]),
            material=int(weights["material"]),
            color=int(weights["color"]),
            hardware=int(weights["hardware"]),
            title_similarity=int(weights["title_similarity"]),
            title_token=int(weights["title_token"]),
            model_family=int(weights["model_family"]),
            condition=int(weights["condition"]),
        ),
        thresholds=MatchingThresholds(
            accept_threshold=int(thresholds.get("accept_threshold", 70)),
            near_miss_threshold=int(thresholds.get("near_miss_threshold", 45)),
        ),
        hard_reject=MatchingHardReject(
            different_model_number=bool(hard_reject["different_model_number"]),
            category_conflict=bool(hard_reject["category_conflict"]),
            material_conflict=bool(hard_reject["material_conflict"]),
        ),
    )


@lru_cache(maxsize=1)
def get_matching_config() -> MatchingConfig:
    """Cached default matching configuration."""
    return load_matching_config()
