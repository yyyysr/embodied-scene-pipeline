from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Check an existing local model runtime")
    parser.add_argument("--backend", choices=["sd35", "trellis"], default="sd35")
    parser.add_argument(
        "--python",
        help="Python interpreter that already contains the selected model dependencies",
    )
    parser.add_argument(
        "--attention-backend", choices=["flash-attn", "xformers"], default="flash-attn"
    )
    args = parser.parse_args()
    repository_root = Path(__file__).resolve().parents[1]
    environment_name = (
        "EMBODIED_SCENE_LOCAL_ASSET_PYTHON"
        if args.backend == "sd35"
        else "EMBODIED_SCENE_LOCAL_TRELLIS_PYTHON"
    )
    python_executable = args.python or os.environ.get(environment_name) or sys.executable
    worker = repository_root / "local_runtime" / f"{args.backend}_worker.py"
    command = [python_executable, str(worker), "--check"]
    environment = os.environ.copy()
    cwd = None
    if args.backend == "trellis":
        command.extend(["--attention-backend", args.attention_backend])
        trellis_repo = Path(
            os.environ.get(
                "EMBODIED_SCENE_TRELLIS_REPO_DIR",
                repository_root / "third_party" / "TRELLIS",
            )
        ).resolve()
        if not (trellis_repo / "trellis").is_dir():
            raise SystemExit(f"TRELLIS submodule is not initialized: {trellis_repo}")
        existing = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = os.pathsep.join(
            value for value in (str(trellis_repo), existing) if value
        )
        cwd = trellis_repo
    with tempfile.TemporaryDirectory(prefix="local-runtime-check-") as cache_root:
        if args.backend == "trellis":
            environment["NUMBA_CACHE_DIR"] = str(Path(cache_root) / "numba")
            environment["WARP_CACHE_PATH"] = str(Path(cache_root) / "warp")
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            env=environment,
            cwd=cwd,
        )
    if completed.returncode != 0:
        raise SystemExit((completed.stderr or completed.stdout).strip())
    result = json.loads(completed.stdout)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
