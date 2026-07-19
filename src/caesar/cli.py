"""Command-line entry point for Caesar."""

import argparse
from importlib.metadata import version

VERSION = version("caesar-ai")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="caesar",
        description="A personal AI agent that talks to you over Telegram.",
    )
    parser.add_argument("--version", action="version", version=f"caesar {VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run", help="Start the agent (stub in this version).")
    return parser


def main() -> int:
    build_parser().parse_args()
    print(
        f"Caesar v{VERSION} — ave! "
        "The agent itself is still being forged; nothing to run yet."
    )
    return 0
