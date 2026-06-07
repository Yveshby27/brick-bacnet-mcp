"""CLI entry point: `brick-bacnet-mcp --config path/to/config.yaml`."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from brick_bacnet_mcp import __version__
from brick_bacnet_mcp.config import load_config
from brick_bacnet_mcp.server import run_blocking, run_coverage_report_blocking


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="brick-bacnet-mcp",
        description=(
            "Read-only BACnet/IP gateway exposing Brick + Haystack tagged " "topology via MCP."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to YAML config file (default: ./config.yaml)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="Override log level from config",
    )
    parser.add_argument(
        "--coverage-report",
        action="store_true",
        help=(
            "Run one discover + tag cycle, print a rule-coverage diagnostic, and exit. "
            "Use this to see what fraction of your building's points the rule library "
            "matched and which names need new rules."
        ),
    )
    parser.add_argument(
        "--top-unmatched",
        type=int,
        default=20,
        help="Number of unmatched object names to list in the coverage report (default: 20)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"brick-bacnet-mcp {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    if args.log_level:
        config.log_level = args.log_level
    _setup_logging(config.log_level)
    if args.coverage_report:
        report = run_coverage_report_blocking(config, top_n=args.top_unmatched)
        print(report.render_text())
        return 0
    run_blocking(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
