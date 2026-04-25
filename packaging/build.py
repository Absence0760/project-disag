"""Cross-platform PyInstaller build driver.

Builds single-file executables for both `disag` and `exceed` on whatever OS
this script is run on. PyInstaller does not cross-compile -- to produce
binaries for all three platforms (Windows / macOS / Ubuntu), run this
script on each OS, or use the GitHub Actions workflow at
`.github/workflows/release.yml`.

Usage
-----
    python3 packaging/build.py             # build both apps for current OS
    python3 packaging/build.py --app disag # build only disag
    python3 packaging/build.py --clean     # remove build/ and dist/ first
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPS = ("disag", "exceed")


def _ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.exit(
            "PyInstaller is not installed. Install it with:\n"
            "    pip install pyinstaller\n"
            "(use a virtualenv if your system Python is externally managed)."
        )


def _clean(paths: list[Path]) -> None:
    for p in paths:
        if p.exists():
            print(f"removing {p}")
            shutil.rmtree(p)


def _build_one(app: str) -> Path:
    launcher = ROOT / "packaging" / f"{app}_launcher.py"
    if not launcher.exists():
        sys.exit(f"missing launcher: {launcher}")

    # `--onefile` packs everything into a single executable; works on all
    # three OSes. We do *not* use `--windowed` because both apps still
    # support a `--no-gui` CLI mode, which needs stdio.
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--name", app,
        "--paths", str(ROOT),
        "--workpath", str(ROOT / "build"),
        "--distpath", str(ROOT / "dist"),
        "--specpath", str(ROOT / "build"),
        str(launcher),
    ]
    print(">", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)

    suffix = ".exe" if platform.system() == "Windows" else ""
    out = ROOT / "dist" / f"{app}{suffix}"
    if not out.exists():
        sys.exit(f"build claimed success but {out} is missing")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--app", choices=APPS, help="Build only one app")
    parser.add_argument("--clean", action="store_true",
                        help="Remove build/ and dist/ before building")
    args = parser.parse_args()

    _ensure_pyinstaller()

    if args.clean:
        _clean([ROOT / "build", ROOT / "dist"])

    targets = (args.app,) if args.app else APPS
    artifacts = [_build_one(app) for app in targets]

    print()
    print(f"Built {len(artifacts)} executable(s) on {platform.system()} "
          f"{platform.machine()}:")
    for a in artifacts:
        size_mb = a.stat().st_size / 1024 / 1024
        print(f"  {a.relative_to(ROOT)}  ({size_mb:.1f} MiB)")


if __name__ == "__main__":
    main()
