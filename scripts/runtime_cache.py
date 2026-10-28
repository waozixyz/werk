#!/usr/bin/env python3
"""Keep generated runtime objects tied to one toolchain checkout."""
from pathlib import Path
import shutil
import subprocess
import sys


def prepare(source, output):
    root = Path(__file__).resolve().parents[1]
    source = Path(source).resolve()
    output = Path(output).resolve()
    if (not output.is_relative_to(root) or output.name not in {"ziran", "web-runtime", "bundle-runtime"}
            or not any(output.is_relative_to(root / parent) for parent in ("build", "droid/app/.cxx", "droid/app/build"))):
        raise ValueError("Runtime cache must be an owned build intermediate")
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    identity = str(source) + "\n" + revision + "\n"
    marker = output / ".toolchain"
    if marker.is_file() and marker.read_text() == identity:
        return
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    marker.write_text(identity)


if __name__ == "__main__":
    prepare(*sys.argv[1:])
