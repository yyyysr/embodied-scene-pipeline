from __future__ import annotations

import argparse
from pathlib import Path

from embodied_scene.usd.pipeline import validate_usd, write_json


def main():
    parser = argparse.ArgumentParser(description="Run USD static checks; no simulator")
    parser.add_argument("scene", type=Path)
    parser.add_argument(
        "--report",
        type=Path,
    )
    args = parser.parse_args()
    report = validate_usd(args.scene.resolve())
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.report, report)
    print(report)
    raise SystemExit(0 if report["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
