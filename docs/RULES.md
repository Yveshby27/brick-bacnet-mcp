# Rule grammar and override conventions

This document covers how the Brick + Haystack tagger rules work, the file
format, the matching semantics, and how to extend the default library.

## File location

Default rule files ship inside the package:

```
src/brick_bacnet_mcp/rules/brick_rules.yaml
src/brick_bacnet_mcp/rules/haystack_rules.yaml
```

Point `config.yaml` at custom paths to override:

```yaml
rules:
  brick: /etc/brick-bacnet-mcp/site_brick_rules.yaml
  haystack: /etc/brick-bacnet-mcp/site_haystack_rules.yaml
```

## File format

Each file is a YAML list of rule entries. Required and optional fields per
entry:

| Field | Required | Type | Purpose |
|---|---|---|---|
| `id` | optional (auto-assigned) | str | Stable identifier used in TaggedObject.rule_matched, debugging, error messages |
| `pattern` | required | str | Regex matched against the BACnet object's `objectName` property |
| `units` | optional | list of str | Substrings checked against the object's `units` field (case-insensitive); empty list means units are not constrained |
| `object_types` | optional | list of str | Canonical BACnet object-type strings the rule applies to; empty list means all types |
| `brick_class` | Brick file only | str | Brick class IRI fragment assigned on match |
| `haystack_tags` | Haystack file only | list of str | Haystack tag set assigned on match |
| `haystack_kind` | Haystack file optional | str | Haystack "kind" tag (Number, Bool, Str, Marker) |
| `haystack_unit` | Haystack file optional | str | Normalized Haystack unit string |

## Matching semantics

For each object the tagger considers each rule in file order. A rule matches
when ALL of the following are true:

1. `re.search(rule.pattern, obj.object_name)` returns a match
2. If `rule.units` is non-empty, at least one entry appears as a substring
   (case-insensitive) of `obj.units`
3. If `rule.object_types` is non-empty, `obj.object_type` is one of them

First match wins; the tagger does NOT evaluate further rules in the same file
once a match is found.

This means rule order matters: more specific rules should appear before more
general ones. The starter library follows this convention; the generic
"temperature catch-all" appears at the bottom.

## Object-type canonical strings

The tagger expects BACnet object types as kebab-case strings:

- `analog-input`
- `analog-output`
- `analog-value`
- `binary-input`
- `binary-output`
- `binary-value`
- `multi-state-input`
- `multi-state-output`
- `multi-state-value`
- `schedule`
- `calendar`
- `notification-class`

If your rules use a different convention, the reader will not feed them
matching object-type values and the rules will never match. Use the canonical
strings above.

## Regex patterns

Patterns are evaluated by Python's `re.search`. Common patterns in the starter
library:

- Case-insensitive prefix: `(?i)^OAT$`
- Word-boundary match anywhere in name: `(?i)\b(oat|outside_air_temp)\b`
- Allow underscore or space as separator: `(?i)\b(zone[_ ]?temp|znt)\b`
- Allow numeric suffix: `(?i)\b(ahu|air_handler)[_ ]?\d*\b`

If your site uses vendor-specific naming (e.g. Trane `RmTmp`, JCI `ZN-T`,
Niagara `discharge.temp.001`), add patterns specific to those conventions in a
site-local rule file. Default patterns intentionally cover the most common
shorthand vocabulary across vendors.

## Extending the library

To add coverage for a new object pattern:

1. Decide the Brick class fragment and the Haystack tag set
2. Add an entry to `brick_rules.yaml` and `haystack_rules.yaml`
3. Add a parametrized test case in `tests/test_tagger.py`
4. Run `pytest tests/test_tagger.py` to confirm the rule matches the intended
   pattern AND does not collide with existing rules
5. Open a PR

Pattern overlap is the main risk when extending. If two rules can match the
same name, file order determines which wins. When adding a more-specific rule,
place it ABOVE the general catch-all rules that already cover the pattern.

## Site-specific overrides

For deployments where the default library is wrong (vendor-specific naming
convention, custom semantic vocabulary), copy the default files to a local
location, edit, and point config at the copies:

```yaml
rules:
  brick: /etc/brick-bacnet-mcp/site_brick_rules.yaml
  haystack: /etc/brick-bacnet-mcp/site_haystack_rules.yaml
```

Local files take complete precedence over the bundled library. To mix-and-
match, include any default rules you still want in your local file (the
loader does not merge across files).

## Debugging unmatched objects

When an object should match but does not, run example 02:

```bash
python examples/02_tag_one_ahu.py --config examples/config_example.yaml
```

It prints all untagged objects on the AHU device, which surfaces gaps in the
rule library. Common causes:

- Object name uses an unexpected separator (e.g. dot instead of underscore)
- Object name carries vendor-specific shorthand the pattern does not cover
- Units string is empty when the rule has a `units` constraint
- Object type does not match `object_types` restriction
