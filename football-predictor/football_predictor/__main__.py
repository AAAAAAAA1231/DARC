from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="西甲/德甲/意甲胜负推理")
    parser.add_argument("--cli", action="store_true", help="命令行模式")
    parser.add_argument("cli_args", nargs=argparse.REMAINDER, help="传给 CLI 的参数")
    args = parser.parse_args(argv)
    if args.cli:
        from football_predictor.cli import run_cli

        extra = args.cli_args
        if extra and extra[0] == "--":
            extra = extra[1:]
        return run_cli(extra)
    from football_predictor.ui.app import main as gui_main

    gui_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
