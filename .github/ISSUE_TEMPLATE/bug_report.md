---
name: Bug report
about: Report something that doesn't work as documented
title: '[bug] '
labels: bug
assignees: ''
---

## What happened

A clear description of what went wrong.

## What you expected

What you thought would happen instead.

## Environment

- brick-bacnet-mcp version (or commit hash):
- Python version (`python --version`):
- OS (Windows / macOS / Linux + version):
- bacpypes3 version (`pip show bacpypes3 | grep Version`):
- fastmcp version (`pip show fastmcp | grep Version`):
- MCP host (Claude Desktop, Cursor, custom, etc.):

## BACnet context (if relevant)

- Real network or the included simulator?
- Vendor(s) of the controllers involved (JCI Metasys, Tridium Niagara, Siemens Apogee, Honeywell, Distech, etc.):
- Object types involved (analog-input, binary-output, multi-state-value, etc.):
- A representative object name pattern (e.g., `AHU01_DAT_001` or `B1.AHU1.SAT`):

## Reproduction steps

1.
2.
3.

## Logs / error output

```
paste relevant log lines or traceback here
```

## Anything else

Screenshots, config snippets (with secrets redacted), related issues, hypothesis on root cause.
