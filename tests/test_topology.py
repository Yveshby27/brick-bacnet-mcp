"""Tests for the TopologyAssembler + Topology model filters."""

from __future__ import annotations

from pathlib import Path

from brick_bacnet_mcp.models import BACnetDevice, BACnetObject, Topology
from brick_bacnet_mcp.tagger import Tagger
from brick_bacnet_mcp.topology import TopologyAssembler


def _sample_objects(device_instance: int) -> list[BACnetObject]:
    return [
        BACnetObject(
            device_instance=device_instance,
            object_type="analog-input",
            object_instance=1,
            object_name="OAT",
            units="degF",
            present_value=72.4,
        ),
        BACnetObject(
            device_instance=device_instance,
            object_type="analog-input",
            object_instance=2,
            object_name="zone_temp_3",
            units="degF",
            present_value=70.0,
        ),
        BACnetObject(
            device_instance=device_instance,
            object_type="multi-state-value",
            object_instance=3,
            object_name="AHU_1",
        ),
    ]


def test_assemble_tags_all_objects(brick_rules_path: Path, haystack_rules_path: Path) -> None:
    tagger = Tagger(brick_rules_path, haystack_rules_path)
    assembler = TopologyAssembler(tagger)
    device = BACnetDevice(device_instance=100, address="192.168.1.100:47808")
    objs = _sample_objects(100)

    topology = assembler.assemble([device], {100: objs})
    assert len(topology.devices) == 1
    assert len(topology.tagged_objects) == 3
    assert any(t.brick_class == "Outside_Air_Temperature_Sensor" for t in topology.tagged_objects)
    assert any(t.brick_class == "Zone_Air_Temperature_Sensor" for t in topology.tagged_objects)
    assert any(t.brick_class == "AHU" for t in topology.tagged_objects)


def test_topology_filter_by_brick(brick_rules_path: Path, haystack_rules_path: Path) -> None:
    tagger = Tagger(brick_rules_path, haystack_rules_path)
    assembler = TopologyAssembler(tagger)
    device = BACnetDevice(device_instance=100, address="192.168.1.100:47808")
    topology = assembler.assemble([device], {100: _sample_objects(100)})

    filtered = topology.filter_by_brick("Outside_Air_Temperature_Sensor")
    assert len(filtered.tagged_objects) == 1
    assert filtered.tagged_objects[0].object.object_name == "OAT"
    assert len(filtered.devices) == 1


def test_topology_filter_by_haystack(brick_rules_path: Path, haystack_rules_path: Path) -> None:
    tagger = Tagger(brick_rules_path, haystack_rules_path)
    assembler = TopologyAssembler(tagger)
    device = BACnetDevice(device_instance=100, address="192.168.1.100:47808")
    topology = assembler.assemble([device], {100: _sample_objects(100)})

    filtered = topology.filter_by_haystack("outside", "air", "temp")
    assert len(filtered.tagged_objects) == 1
    assert filtered.tagged_objects[0].brick_class == "Outside_Air_Temperature_Sensor"


def test_topology_summary(brick_rules_path: Path, haystack_rules_path: Path) -> None:
    tagger = Tagger(brick_rules_path, haystack_rules_path)
    assembler = TopologyAssembler(tagger)
    device = BACnetDevice(device_instance=100, address="192.168.1.100:47808")
    topology = assembler.assemble([device], {100: _sample_objects(100)})

    summary = topology.to_summary()
    assert summary["device_count"] == 1
    assert summary["object_count"] == 3
    assert "Outside_Air_Temperature_Sensor" in summary["brick_classes"]
    assert "outside" in summary["haystack_tag_set"]
    assert "ahu" in summary["haystack_tag_set"]


def test_empty_topology() -> None:
    topology = Topology()
    assert topology.to_summary() == {
        "device_count": 0,
        "object_count": 0,
        "brick_classes": [],
        "haystack_tag_set": [],
    }
