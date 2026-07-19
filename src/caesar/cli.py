"""Command-line entry point for Caesar."""

import argparse
import asyncio
import logging
import sys
from importlib.metadata import version

from caesar.channel import ChannelError, TelegramChannel
from caesar.config import ConfigError, load_agent_config, resolve_agent_dir
from caesar.telegram import PollingTelegramTransport

VERSION = version("caesar-ai")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="caesar",
        description="A personal AI agent that talks to you over Telegram.",
    )
    parser.add_argument("--version", action="version", version=f"caesar {VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Start the agent.")
    run.add_argument(
        "agent_dir",
        nargs="?",
        help="Agent directory (defaults to $CAESAR_AGENTS, then the current "
        "directory if it contains agent.yml).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
    )

    try:
        agent_dir = resolve_agent_dir(args.agent_dir)
        config = load_agent_config(agent_dir)
        transport = PollingTelegramTransport(config.telegram.token)
        channel = TelegramChannel(transport, config.telegram.allowed_user_ids)
        print(f"{config.name} is listening on Telegram. Press Ctrl-C to stop.")
        asyncio.run(channel.start())
    except (ConfigError, ChannelError) as error:
        print(f"caesar: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Vale! Caesar stopped.")
    return 0
