"""Unit tests for the Brick + Haystack rule-based tagger.

The starter rule library at `src/brick_bacnet_mcp/rules/` is the test target.
If you extend the library, add a test case here verifying the new rule matches
its intended pattern AND does not collide with existing rules.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from brick_bacnet_mcp.models import BACnetObject
from brick_bacnet_mcp.tagger import Tagger, TaggingRule, compute_coverage

# ---------- Tagger construction ----------


def test_tagger_loads_default_rules(brick_rules_path: Path, haystack_rules_path: Path) -> None:
    tagger = Tagger(brick_rules_path, haystack_rules_path)
    counts = tagger.rule_count
    assert counts["brick"] > 30, f"Expected 30+ Brick rules, got {counts['brick']}"
    assert counts["haystack"] > 25, f"Expected 25+ Haystack rules, got {counts['haystack']}"


def test_tagger_missing_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yaml"
    with pytest.raises(FileNotFoundError):
        Tagger(brick_rules_path=missing)


def test_tagger_loads_partial(brick_rules_path: Path) -> None:
    """Brick-only construction should work (Haystack rules optional)."""
    tagger = Tagger(brick_rules_path=brick_rules_path)
    assert tagger.rule_count["brick"] > 0
    assert tagger.rule_count["haystack"] == 0


# ---------- Brick rule matches ----------


@pytest.mark.parametrize(
    "name, units, expected_brick",
    [
        ("OAT", "degF", "Outside_Air_Temperature_Sensor"),
        ("outside_air_temp", "°F", "Outside_Air_Temperature_Sensor"),
        ("DAT", "degF", "Supply_Air_Temperature_Sensor"),
        ("SAT_001", "degF", "Supply_Air_Temperature_Sensor"),
        ("zone_temp", "degF", "Zone_Air_Temperature_Sensor"),
        ("ZNT_2", "degF", "Zone_Air_Temperature_Sensor"),
        ("zone_co2", "ppm", "CO2_Sensor"),
        ("CHWS_TEMP", "degF", "Chilled_Water_Supply_Temperature_Sensor"),
        ("HWR_TEMP", "degF", "Hot_Water_Return_Temperature_Sensor"),
        ("AHU_1", "", "AHU"),
        ("RTU-2", "", "RTU"),
        ("kWh_meter", "kWh", "Electrical_Power_Sensor"),
    ],
)
def test_brick_known_patterns(
    brick_rules_path: Path,
    haystack_rules_path: Path,
    name: str,
    units: str,
    expected_brick: str,
) -> None:
    tagger = Tagger(brick_rules_path, haystack_rules_path)
    obj = BACnetObject(
        device_instance=1,
        object_type="analog-input",
        object_instance=1,
        object_name=name,
        units=units,
    )
    tagged = tagger.tag(obj)
    assert (
        tagged.brick_class == expected_brick
    ), f"Expected Brick class {expected_brick} for '{name}'; got {tagged.brick_class}"


def test_brick_no_match_returns_none(brick_rules_path: Path, haystack_rules_path: Path) -> None:
    tagger = Tagger(brick_rules_path, haystack_rules_path)
    obj = BACnetObject(
        device_instance=1,
        object_type="analog-input",
        object_instance=999,
        object_name="garbleblargh-unmatched-pattern",
        units="lumens",
    )
    tagged = tagger.tag(obj)
    assert tagged.brick_class is None
    assert tagged.haystack_tags == []


def test_object_type_restriction(brick_rules_path: Path, haystack_rules_path: Path) -> None:
    """Supply-fan Brick rule is restricted to binary/multi-state types."""
    tagger = Tagger(brick_rules_path, haystack_rules_path)
    obj_analog = BACnetObject(
        device_instance=1,
        object_type="analog-input",
        object_instance=1,
        object_name="SF_status",
    )
    obj_binary = BACnetObject(
        device_instance=1,
        object_type="binary-input",
        object_instance=1,
        object_name="SF_status",
    )
    assert tagger.tag(obj_analog).brick_class != "Supply_Fan"
    assert tagger.tag(obj_binary).brick_class == "Supply_Fan"


# ---------- Haystack rule matches ----------


def test_haystack_oat_tags(brick_rules_path: Path, haystack_rules_path: Path) -> None:
    tagger = Tagger(brick_rules_path, haystack_rules_path)
    obj = BACnetObject(
        device_instance=1,
        object_type="analog-input",
        object_instance=1,
        object_name="OAT",
        units="degF",
    )
    tagged = tagger.tag(obj)
    assert set(tagged.haystack_tags) == {"point", "sensor", "outside", "air", "temp"}
    assert tagged.haystack_kind == "Number"
    assert tagged.haystack_unit == "°F"


def test_haystack_equip_marker(brick_rules_path: Path, haystack_rules_path: Path) -> None:
    tagger = Tagger(brick_rules_path, haystack_rules_path)
    obj = BACnetObject(
        device_instance=1,
        object_type="multi-state-value",
        object_instance=1,
        object_name="AHU_1",
    )
    tagged = tagger.tag(obj)
    assert "equip" in tagged.haystack_tags
    assert "ahu" in tagged.haystack_tags
    assert tagged.haystack_kind == "Marker"


# ---------- Custom rule injection ----------


def test_add_custom_brick_rule(brick_rules_path: Path) -> None:
    tagger = Tagger(brick_rules_path=brick_rules_path)
    rule = TaggingRule(
        id="custom:wibble",
        pattern=r"(?i)^wibble$",
        brick_class="Wibble_Sensor",
    )
    tagger.add_brick_rule(rule)
    obj = BACnetObject(
        device_instance=1,
        object_type="analog-input",
        object_instance=1,
        object_name="WIBBLE",
    )
    tagged = tagger.tag(obj)
    assert tagged.brick_class == "Wibble_Sensor"


# ---------- Rule file integrity ----------


def test_rule_ids_unique_within_file(brick_rules_path: Path) -> None:
    """Catch typo-duplicated rule IDs which would cause silent shadowing."""
    tagger = Tagger(brick_rules_path=brick_rules_path)
    ids = [r.id for r in tagger.brick_rules]
    assert len(ids) == len(set(ids)), f"Duplicate Brick rule IDs: {sorted(ids)}"


def test_all_brick_rules_have_brick_class(brick_rules_path: Path) -> None:
    tagger = Tagger(brick_rules_path=brick_rules_path)
    for rule in tagger.brick_rules:
        assert (
            rule.brick_class is not None and rule.brick_class != ""
        ), f"Brick rule {rule.id} missing brick_class"


def test_all_haystack_rules_have_tags(haystack_rules_path: Path) -> None:
    tagger = Tagger(haystack_rules_path=haystack_rules_path)
    for rule in tagger.haystack_rules:
        assert rule.haystack_tags, f"Haystack rule {rule.id} has empty haystack_tags"


# ---------- Coverage report ----------


def _mk_obj(name: str | None, units: str = "degF", instance: int = 1) -> BACnetObject:
    return BACnetObject(
        device_instance=1,
        object_type="analog-input",
        object_instance=instance,
        object_name=name,
        units=units,
    )


def test_compute_coverage_empty() -> None:
    report = compute_coverage([])
    assert report.total_objects == 0
    assert report.matched_brick == 0
    assert report.matched_haystack == 0
    assert report.brick_coverage_pct == 0.0
    assert report.top_unmatched_names == []
    assert report.rule_hit_counts == {}


def test_compute_coverage_mixed(brick_rules_path: Path, haystack_rules_path: Path) -> None:
    tagger = Tagger(brick_rules_path, haystack_rules_path)
    objects = [
        _mk_obj("OAT", "degF", 1),
        _mk_obj("DAT", "degF", 2),
        _mk_obj("zone_temp", "degF", 3),
        _mk_obj("garbleblargh_unmatched", "lumens", 4),
        _mk_obj("another_garble", "lumens", 5),
    ]
    tagged = tagger.tag_many(objects)
    report = compute_coverage(tagged)

    assert report.total_objects == 5
    assert report.matched_brick == 3
    assert report.matched_haystack == 3
    assert report.matched_both == 3
    assert report.matched_either == 3
    assert report.brick_coverage_pct == 60.0
    assert report.haystack_coverage_pct == 60.0
    unmatched_names = {entry.name for entry in report.top_unmatched_names}
    assert unmatched_names == {"garbleblargh_unmatched", "another_garble"}


def test_compute_coverage_unmatched_grouping(
    brick_rules_path: Path, haystack_rules_path: Path
) -> None:
    """Repeated unmatched names should group into one entry with count."""
    tagger = Tagger(brick_rules_path, haystack_rules_path)
    objects = [_mk_obj("weird_point", "lumens", i) for i in range(5)]
    objects.append(_mk_obj("other_weird", "lumens", 99))
    tagged = tagger.tag_many(objects)
    report = compute_coverage(tagged)

    assert report.total_objects == 6
    assert report.matched_either == 0
    by_name = {entry.name: entry.count for entry in report.top_unmatched_names}
    assert by_name == {"weird_point": 5, "other_weird": 1}


def test_compute_coverage_rule_hit_counts(
    brick_rules_path: Path, haystack_rules_path: Path
) -> None:
    tagger = Tagger(brick_rules_path, haystack_rules_path)
    objects = [_mk_obj("OAT", "degF", i) for i in range(3)]
    tagged = tagger.tag_many(objects)
    report = compute_coverage(tagged)

    assert sum(report.rule_hit_counts.values()) == 3
    oat_hit = next(
        (n for rule_id, n in report.rule_hit_counts.items() if "brick:oat" in rule_id),
        None,
    )
    assert oat_hit == 3


def test_coverage_report_render_text_nonempty(
    brick_rules_path: Path, haystack_rules_path: Path
) -> None:
    tagger = Tagger(brick_rules_path, haystack_rules_path)
    tagged = tagger.tag_many([_mk_obj("OAT", "degF", 1), _mk_obj("nope", "lumens", 2)])
    report = compute_coverage(tagged)
    text = report.render_text()

    assert "coverage report" in text.lower()
    assert "50.0%" in text
    assert "nope" in text


def test_coverage_report_render_text_empty() -> None:
    text = compute_coverage([]).render_text()
    assert "No objects discovered" in text
