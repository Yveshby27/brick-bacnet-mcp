"""Rule-based Brick + Haystack semantic tagger.

Reads YAML rule files defining (pattern, units, output) tuples and applies them
to BACnet objects to produce TaggedObject instances. Rules are evaluated in
file order; the first match wins per rule file. Users override the default
library by editing the YAML files in `src/brick_bacnet_mcp/rules/` (or pointing
at custom paths via config).
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from brick_bacnet_mcp.models import BACnetObject, TaggedObject

logger = logging.getLogger(__name__)


class TaggingRule(BaseModel):
    """One rule from a Brick or Haystack rules YAML file.

    Pattern is a regex applied to the object's name (case-insensitive by default
    if the pattern uses `(?i)`); units is a list of acceptable unit strings,
    matched if the object's units field contains any one as substring (case-
    insensitive). object_types optionally restricts the rule to specific BACnet
    object types.
    """

    id: str = Field(..., description="Stable rule identifier for debugging")
    pattern: str = Field(..., description="Regex matched against object name")
    units: list[str] = Field(
        default_factory=list,
        description=(
            "Optional list of acceptable unit substrings. "
            "Empty list means unit is not a constraint."
        ),
    )
    object_types: list[str] = Field(
        default_factory=list,
        description=(
            "Optional list of BACnet object types this rule applies to. "
            "Empty means any object type."
        ),
    )
    # Brick output
    brick_class: str | None = Field(
        default=None, description="Brick class fragment to assign if matched"
    )
    # Haystack output
    haystack_tags: list[str] = Field(
        default_factory=list,
        description="Haystack tag set to assign if matched",
    )
    haystack_kind: str | None = Field(
        default=None, description="Haystack 'kind' tag (Number, Bool, Str, Marker)"
    )
    haystack_unit: str | None = Field(
        default=None, description="Normalized Haystack unit string if matched"
    )


class Tagger:
    """Applies tagging rules to BACnet objects.

    Construct with one or two rule files (Brick + Haystack). Rules are loaded
    eagerly; mutate via `add_rule` if needed.
    """

    def __init__(
        self,
        brick_rules_path: str | Path | None = None,
        haystack_rules_path: str | Path | None = None,
    ) -> None:
        self.brick_rules: list[TaggingRule] = []
        self.haystack_rules: list[TaggingRule] = []
        if brick_rules_path:
            self.brick_rules = self._load_rules(brick_rules_path)
        if haystack_rules_path:
            self.haystack_rules = self._load_rules(haystack_rules_path)

    @staticmethod
    def _load_rules(path: str | Path) -> list[TaggingRule]:
        """Read a YAML rule file into TaggingRule instances."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Rule file not found: {p}")
        with p.open("r", encoding="utf-8") as f:
            raw: Any = yaml.safe_load(f)
        if not isinstance(raw, list):
            raise ValueError(f"Rule file {p} must be a YAML list of rule entries; got {type(raw)}")
        rules: list[TaggingRule] = []
        for i, entry in enumerate(raw):
            if not isinstance(entry, dict):
                raise ValueError(f"Rule entry {i} in {p} must be a mapping")
            if "id" not in entry:
                entry["id"] = f"{p.stem}:{i}"
            rules.append(TaggingRule.model_validate(entry))
        logger.info("Loaded %d rules from %s", len(rules), p)
        return rules

    def add_brick_rule(self, rule: TaggingRule) -> None:
        self.brick_rules.append(rule)

    def add_haystack_rule(self, rule: TaggingRule) -> None:
        self.haystack_rules.append(rule)

    def tag(self, obj: BACnetObject) -> TaggedObject:
        """Apply Brick + Haystack rule libraries to a single object.

        Returns a TaggedObject. If no rules match, brick_class is None and
        haystack_tags is empty.
        """
        brick_rule = self._first_match(obj, self.brick_rules)
        haystack_rule = self._first_match(obj, self.haystack_rules)

        tagged = TaggedObject(
            object=obj,
            brick_class=brick_rule.brick_class if brick_rule else None,
            haystack_tags=list(haystack_rule.haystack_tags) if haystack_rule else [],
            haystack_kind=haystack_rule.haystack_kind if haystack_rule else None,
            haystack_unit=haystack_rule.haystack_unit if haystack_rule else None,
            rule_matched=self._compose_rule_match(brick_rule, haystack_rule),
        )
        return tagged

    def tag_many(self, objects: list[BACnetObject]) -> list[TaggedObject]:
        return [self.tag(obj) for obj in objects]

    @staticmethod
    def _first_match(obj: BACnetObject, rules: list[TaggingRule]) -> TaggingRule | None:
        """Return the first rule whose pattern + units + object_types match."""
        name = obj.object_name or ""
        units = obj.units or ""
        otype = obj.object_type
        for rule in rules:
            # Object-type restriction
            if rule.object_types and otype not in rule.object_types:
                continue
            # Pattern match (regex against object name)
            try:
                if not re.search(rule.pattern, name):
                    continue
            except re.error:
                logger.warning("Invalid regex in rule %s: %s", rule.id, rule.pattern)
                continue
            # Units constraint (substring match, case-insensitive)
            if rule.units:
                units_lower = units.lower()
                if not any(u.lower() in units_lower for u in rule.units):
                    continue
            return rule
        return None

    @staticmethod
    def _compose_rule_match(brick: TaggingRule | None, haystack: TaggingRule | None) -> str | None:
        parts: list[str] = []
        if brick:
            parts.append(f"brick={brick.id}")
        if haystack:
            parts.append(f"haystack={haystack.id}")
        return "; ".join(parts) if parts else None

    @property
    def rule_count(self) -> dict[str, int]:
        return {"brick": len(self.brick_rules), "haystack": len(self.haystack_rules)}


class UnmatchedName(BaseModel):
    """One entry in the top-unmatched-names list of a CoverageReport."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Raw object name that no rule matched")
    count: int = Field(..., ge=1, description="Number of objects with this exact name")


class CoverageReport(BaseModel):
    """Diagnostic summary of how well the rule library matched a tagging run.

    Built post-hoc from a list of TaggedObject; the goal is to give an MSI
    cloning the repo a 60-second answer to "is this tool broken or are my
    rules just thin for my naming convention." Without this report, an
    unmatched-heavy first run is silent failure.
    """

    model_config = ConfigDict(extra="forbid")

    total_objects: int = Field(..., ge=0, description="Total tagged objects in this run")
    matched_brick: int = Field(..., ge=0, description="Objects with a non-null brick_class")
    matched_haystack: int = Field(..., ge=0, description="Objects with at least one haystack_tag")
    matched_either: int = Field(..., ge=0, description="Objects matched by Brick OR Haystack")
    matched_both: int = Field(..., ge=0, description="Objects matched by Brick AND Haystack")
    brick_coverage_pct: float = Field(..., ge=0.0, le=100.0)
    haystack_coverage_pct: float = Field(..., ge=0.0, le=100.0)
    top_unmatched_names: list[UnmatchedName] = Field(
        default_factory=list,
        description="Most-common object names that no rule matched, descending by count",
    )
    rule_hit_counts: dict[str, int] = Field(
        default_factory=dict,
        description="rule_matched string -> count. Zero-hit rules suggest dead patterns.",
    )

    def render_text(self) -> str:
        """Human-readable report for stdout."""
        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("brick-bacnet-mcp coverage report")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Total objects:     {self.total_objects}")
        if self.total_objects == 0:
            lines.append("")
            lines.append(
                "No objects discovered. Check broadcast_address and discovery_timeout_seconds in your config."
            )
            lines.append("=" * 60)
            return "\n".join(lines)
        lines.append(
            f"Brick coverage:    {self.matched_brick} / {self.total_objects}"
            f"  ({self.brick_coverage_pct:.1f}%)"
        )
        lines.append(
            f"Haystack coverage: {self.matched_haystack} / {self.total_objects}"
            f"  ({self.haystack_coverage_pct:.1f}%)"
        )
        lines.append(f"Matched both:      {self.matched_both}")
        lines.append(f"Matched either:    {self.matched_either}")
        lines.append(f"Unmatched:         {self.total_objects - self.matched_either}")
        lines.append("")
        if self.top_unmatched_names:
            lines.append("Top unmatched object names (by frequency):")
            for entry in self.top_unmatched_names:
                lines.append(f"  {entry.count:>4}  {entry.name}")
            lines.append("")
            lines.append("Tip: extend src/brick_bacnet_mcp/rules/*.yaml to cover these patterns.")
        else:
            lines.append("All objects matched at least one rule.")
        lines.append("")
        if self.rule_hit_counts:
            top_rules = sorted(self.rule_hit_counts.items(), key=lambda kv: kv[1], reverse=True)[
                :10
            ]
            lines.append("Top rule hits:")
            for rule_id, n in top_rules:
                lines.append(f"  {n:>4}  {rule_id}")
        lines.append("=" * 60)
        return "\n".join(lines)


def compute_coverage(tagged: list[TaggedObject], top_n: int = 20) -> CoverageReport:
    """Summarize how well the rule library matched a tagging run.

    `top_n` caps the unmatched-name list. Objects with object_name=None bucket
    under '<no_name>' so they remain visible in the report.
    """
    total = len(tagged)
    if total == 0:
        return CoverageReport(
            total_objects=0,
            matched_brick=0,
            matched_haystack=0,
            matched_either=0,
            matched_both=0,
            brick_coverage_pct=0.0,
            haystack_coverage_pct=0.0,
        )

    matched_brick = sum(1 for t in tagged if t.brick_class)
    matched_haystack = sum(1 for t in tagged if t.haystack_tags)
    matched_either = sum(1 for t in tagged if t.brick_class or t.haystack_tags)
    matched_both = sum(1 for t in tagged if t.brick_class and t.haystack_tags)

    unmatched_counter: Counter[str] = Counter(
        t.object.object_name or "<no_name>"
        for t in tagged
        if not (t.brick_class or t.haystack_tags)
    )

    rule_counter: Counter[str] = Counter()
    for t in tagged:
        if t.rule_matched:
            rule_counter[t.rule_matched] += 1

    return CoverageReport(
        total_objects=total,
        matched_brick=matched_brick,
        matched_haystack=matched_haystack,
        matched_either=matched_either,
        matched_both=matched_both,
        brick_coverage_pct=round(matched_brick / total * 100, 1),
        haystack_coverage_pct=round(matched_haystack / total * 100, 1),
        top_unmatched_names=[
            UnmatchedName(name=name, count=count)
            for name, count in unmatched_counter.most_common(top_n)
        ],
        rule_hit_counts=dict(rule_counter),
    )
