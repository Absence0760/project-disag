# Building executables for Windows, macOS, and Linux

PyInstaller bundles `disag` and `exceed` into single-file executables that
run with no Python installation on the target machine. **PyInstaller cannot
cross-compile** — to produce a binary for a given OS you must build it on
that OS (or in a container / VM running that OS).

This doc covers four routes:

1. [GitHub Actions matrix](#1-github-actions-recommended) — recommended; one
   tag push produces all three artefacts.
2. [Native build on macOS](#2-native-build-on-macos)
3. [Native build on Windows](#3-native-build-on-windows)
4. [Native build on Linux](#4-native-build-on-linux) (with Docker recipe
   for cross-builds from a Mac/Windows host).

---

## 1. GitHub Actions (recommended)

The workflow at [`.github/workflows/release.yml`](../.github/workflows/release.yml)
runs three matrix jobs (`ubuntu-latest`, `macos-latest`, `windows-latest`),
builds the executables, smoke-tests them, packages them into archives, and
uploads them as build artefacts. When the trigger is a `v*` git tag, it
also creates a GitHub Release with all three archives attached.

```bash
# Tag and push — workflow runs on the tag, attaches binaries to a release
git tag v1.0.0
git push origin v1.0.0
```

You can also trigger it manually from the **Actions** tab without tagging
(via "Run workflow"). Artefacts are downloadable for 90 days even without
a release.

| Artefact | OS / arch | Contains |
|----------|-----------|----------|
| `disag-windows-x64.zip` | Windows x86-64 | `disag.exe`, `exceed.exe` |
| `disag-macos-arm64.tar.gz` | macOS Apple Silicon | `disag`, `exceed` |
| `disag-linux-x64.tar.gz` | Linux x86-64 (Ubuntu 22.04 glibc) | `disag`, `exceed` |

### Adding more architectures

The default matrix covers what most clients need. To extend:

| Need | Add to matrix |
|------|---------------|
| Intel Macs (x86_64) | `os: macos-13` (last x86_64 macOS runner) |
| Older glibc / RHEL 7 / Ubuntu 18 | `os: ubuntu-20.04` (older glibc) |
| Windows ARM64 | `os: windows-11-arm` (preview, may be unstable) |

The runner image determines the target glibc / Windows API level — there
is no `--target-arch` flag in PyInstaller for these.

---

## 2. Native build on macOS

### Prerequisites

```bash
brew install python@3.13 python-tk@3.13
```

Apple's stock Python and Xcode Command Line Tools Python both ship without
a working Tk on macOS 15+. Use Homebrew Python or the build will produce
a binary that crashes on GUI launch.

### Build

```bash
python3.13 -m venv /tmp/disag-build
/tmp/disag-build/bin/pip install pyinstaller
/tmp/disag-build/bin/python packaging/build.py --clean
```

Outputs:

- `dist/disag` (~9 MiB)
- `dist/exceed` (~9 MiB)

Both are single-file executables for the current architecture
(`arm64` on Apple Silicon, `x86_64` on Intel). To produce both, run the
build under Rosetta 2 on an Apple Silicon Mac, or use the `macos-13`
runner in CI.

### Code signing & Gatekeeper

The build produces an **ad-hoc signed** binary. On the developer's own Mac
that's fine. When a *different* Mac downloads the binary from the internet,
macOS attaches the `com.apple.quarantine` extended attribute and Gatekeeper
will refuse to launch it ("cannot be opened because the developer cannot
be verified").

End-user workarounds (no code signing):

```bash
# Option A — strip the quarantine flag
xattr -d com.apple.quarantine ./disag

# Option B — Finder right-click → Open → click "Open" in dialog (one-time)
```

Real fix (for client distribution):

1. Get an [Apple Developer ID](https://developer.apple.com/programs/) ($99/year).
2. Re-sign the binary after build:
   ```bash
   codesign --force --sign "Developer ID Application: Your Name (TEAMID)" \
       --options runtime --timestamp dist/disag
   ```
3. Notarise (required on macOS 10.15+):
   ```bash
   xcrun notarytool submit dist/disag.zip --apple-id you@example.com \
       --team-id TEAMID --password APP_SPECIFIC_PASSWORD --wait
   xcrun stapler staple dist/disag
   ```

The CI workflow does *not* notarise — that requires Apple credentials in
GitHub Secrets. Add a step calling `xcrun notarytool submit` to the macOS
job once you have a Developer ID.

---

## 3. Native build on Windows

### Prerequisites

Install [Python 3.13 from python.org](https://www.python.org/downloads/windows/)
(*not* the Microsoft Store version — it sandboxes file access). Tk is
included.

### Build (PowerShell or `cmd`)

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install pyinstaller
.venv\Scripts\python packaging\build.py --clean
```

Outputs:

- `dist\disag.exe`
- `dist\exceed.exe`

Both are self-contained — no Python install needed on the target Windows
machine.

### SmartScreen warning

Unsigned `.exe` files trigger a SmartScreen "Windows protected your PC"
dialog on first run. End user clicks **More info** → **Run anyway**. To
remove the warning entirely you need an [EV Code Signing certificate](https://docs.microsoft.com/en-us/windows-hardware/drivers/dashboard/get-a-code-signing-certificate)
(~$300–500/year) and to sign with `signtool`.

### Antivirus false positives

PyInstaller bundles its bootloader inside the `.exe`, which sometimes
trips heuristic antivirus engines (especially on first release of a new
binary). If clients report this, the bootloader can be rebuilt from
source — see the
[PyInstaller docs](https://pyinstaller.org/en/stable/bootloader-building.html).

---

## 4. Native build on Linux

### Prerequisites

```bash
sudo apt-get update
sudo apt-get install -y python3.13 python3.13-venv python3-tk tk-dev
```

(Or the equivalent on Fedora/RHEL: `python3-tkinter tk-devel`.)

### Build

```bash
python3.13 -m venv .venv
.venv/bin/pip install pyinstaller
.venv/bin/python packaging/build.py --clean
```

Outputs:

- `dist/disag`
- `dist/exceed`

### glibc compatibility

The binary depends on the glibc on the build host. Building on
**Ubuntu 22.04** produces a binary that runs on Ubuntu 22.04+,
Debian 12+, RHEL 9+, and recent Fedoras — but **not** Ubuntu 18.04
or RHEL 7. To support older distros, build on the oldest target glibc
(use `ubuntu-20.04` or older in CI, or the Docker recipe below).

### Building Linux binaries from a Mac (Docker)

The simplest cross-host workflow: run the Linux build inside a container
on your Mac. This produces a Linux x86-64 binary even if you're on Apple
Silicon, thanks to Rosetta-aware Docker.

```bash
docker run --rm -v "$PWD":/src -w /src --platform linux/amd64 \
    python:3.13-slim bash -c '
        apt-get update -qq &&
        apt-get install -y -qq python3-tk tk-dev &&
        pip install -q pyinstaller &&
        python packaging/build.py --clean
    '
```

The resulting `dist/disag` and `dist/exceed` are Linux x86-64 ELF
binaries built against Debian's glibc 2.36 — broadly compatible with
modern distros. Replace `python:3.13-slim` with `python:3.13-bullseye`
for older glibc (2.31, Ubuntu 20.04 era).

**Note:** the host's `dist/` directory will be overwritten. If you
already have a macOS build there, move it aside first (`mv dist
dist-mac`) before running the Docker recipe.

---

## Verifying a build

After any build:

```bash
# CLI smoke test — should print --help text and exit 0
./dist/disag --help
./dist/exceed --help

# End-to-end test against the fixtures (replace path on Windows)
./dist/disag --no-gui --method 0 \
    --monthly testfiles/SINDILA.MON \
    --daily1  testfiles/RUKOKI-l.DAY \
    --output  /tmp/out.day --report /tmp/out.rep

./dist/exceed --no-gui \
    --monthly testfiles/SINDILA.MON \
    --daily   testfiles/RUKOKI-l.DAY \
    --output  /tmp/exceed.rep
```

Compare `/tmp/out.day` byte-for-byte against a reference file (committed
elsewhere or generated from the source-mode `python -m disag`) to confirm
the binary produces identical output to running from source.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `SIGTRAP` / `Trace trap: 5` on macOS GUI launch | (Now-fixed) Old `__main__.py` did `Tk().destroy()` smoke-test that corrupted state on macOS 26 | Pull latest `main` |
| "developer cannot be verified" on macOS | Gatekeeper / quarantine | `xattr -d com.apple.quarantine ./disag` or notarise (see §2) |
| "Windows protected your PC" SmartScreen | Unsigned `.exe` | Click **More info → Run anyway**, or sign with EV cert |
| `version `GLIBC_2.34' not found` on older Linux | Built on newer glibc than target | Rebuild on older OS / Docker image (§4) |
| GUI binary opens then immediately closes | Tk not bundled (rare) | Rebuild on a host where `python -c "import tkinter"` works without errors |
| Antivirus flags the `.exe` | PyInstaller bootloader heuristic | Submit false-positive report, or rebuild custom bootloader |
