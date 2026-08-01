"""Tests for externalized comparable matching configuration."""

from __future__ import annotations

from marketplace.browser_acquisition import comparable_matching as cm
from marketplace.browser_acquisition.matching_config import get_matching_config, load_matching_config
from marketplace.browser_acquisition.yahoo_comparable import select_best_yahoo_comparable
import inspect


def test_matching_config_matches_prior_constants() -> None:
    config = get_matching_config()
    assert config.weights.model_number == 50
    assert config.weights.brand == 0
    assert config.weights.category == 35
    assert config.weights.category_related == 25
    assert config.weights.material == 20
    assert config.weights.color == 10
    assert config.weights.hardware == 8
    assert config.weights.title_similarity == 12
    assert config.weights.title_token == 3
    assert config.weights.model_family == 20
    assert config.weights.condition == 5
    assert config.thresholds.accept_threshold == 70
    assert config.thresholds.near_miss_threshold == 45
    assert config.hard_reject.different_model_number is True
    assert config.hard_reject.category_conflict is True
    assert config.hard_reject.material_conflict is True


def test_comparable_matching_reads_config_weights_and_thresholds() -> None:
    assert cm.SCORE_MODEL_NUMBER == 50
    assert cm.SCORE_BRAND == 0
    assert cm.SCORE_CATEGORY_EXACT == 35
    assert cm.SCORE_CATEGORY_RELATED == 25
    assert cm.SCORE_MATERIAL == 20
    assert cm.SCORE_COLOR == 10
    assert cm.SCORE_HARDWARE == 8
    assert cm.SCORE_TITLE_CAP == 12
    assert cm.SCORE_TITLE_TOKEN == 3
    assert cm.SCORE_MODEL_FAMILY == 20
    assert cm.SCORE_CONDITION == 5
    assert cm.COMPARABLE_SCORE_THRESHOLD == 70
    assert cm.NEAR_MISS_SCORE_THRESHOLD == 45


def test_load_matching_config_from_explicit_path(tmp_path) -> None:
    path = tmp_path / "matching_config.json"
    path.write_text(
        '{"weights":{"model_number":50,"brand":0,"category":35,"category_related":25,'
        '"material":20,"color":10,"hardware":8,"title_similarity":12,"title_token":3,'
        '"model_family":20,"condition":5},'
        '"thresholds":{"accept_threshold":70,"near_miss_threshold":45},'
        '"hard_reject":{"different_model_number":true,"category_conflict":true,'
        '"material_conflict":true}}',
        encoding="utf-8",
    )
    loaded = load_matching_config(path)
    assert loaded.weights.model_number == 50
    assert loaded.thresholds.accept_threshold == 70
    assert loaded.thresholds.near_miss_threshold == 45
    assert loaded.hard_reject.material_conflict is True


def test_select_best_defaults_use_config_thresholds() -> None:
    source = inspect.getsource(select_best_yahoo_comparable)
    assert "COMPARABLE_SCORE_THRESHOLD" in source
    assert "NEAR_MISS_SCORE_THRESHOLD" in source
