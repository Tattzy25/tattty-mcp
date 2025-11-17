"""Simple CLI helpers for operating the MCP server."""
from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_settings
from .logging_utils import tail_file


def tail_logs(lines: int) -> None:
    settings = load_settings()
    log_path = settings.log_directory / "mcp.log"
    output = tail_file(log_path, lines)
    if not output:
        print(f"No log data at {log_path}")
        return
    print(output.rstrip())


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP management helpers")
    subparsers = parser.add_subparsers(dest="command", required=True)

    tail_parser = subparsers.add_parser("tail-logs", help="Tail the MCP log file")
    tail_parser.add_argument("--lines", type=int, default=100, help="Number of lines to show")

    args = parser.parse_args()

    if args.command == "tail-logs":
        tail_logs(args.lines)


if __name__ == "__main__":
    main()
