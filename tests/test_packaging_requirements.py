"""Guards on packaging/build-requirements.{in,txt} — the release build lock.

release.yml installs the .txt with ``pip install --require-hashes`` on
Linux, macOS and Windows, but that only happens on a tag, so nothing in
PR CI ever exercises the file. Twice now a Dependabot regeneration has
silently dropped PyInstaller's platform-conditional dependencies
(6c21be7 / #82, ceaf717 / #101), breaking the macOS and Windows builds
until someone cut a release and watched it fail.

pip-compile can't prevent it: it resolves for the platform it runs on
and drops requirements whose markers don't match, direct ones included,
and pip-tools 7.x has no --universal. So the .txt carries a
hand-maintained block, and these tests are what notice when it's gone.
"""

import os
import re
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
IN_PATH = os.path.join(ROOT, 'packaging', 'build-requirements.in')
TXT_PATH = os.path.join(ROOT, 'packaging', 'build-requirements.txt')

# PyInstaller pulls these in per-OS. Without them the release build can't
# install at all on that OS in --require-hashes mode.
PLATFORM_PINS = {
    'macholib': 'sys_platform == "darwin"',
    'pefile': 'sys_platform == "win32"',
    'pywin32-ctypes': 'sys_platform == "win32"',
}

# `name==version [; marker] \` — the pinned-requirement line that opens a
# block. Continuation lines are hashes and `# via` comments.
PIN_RE = re.compile(r'^(?P<name>[A-Za-z0-9._-]+)==(?P<version>[^\s;\\]+)(?P<rest>.*)$')


def _read(path):
    with open(path) as fh:
        return fh.read()


def _pins(text):
    """Map requirement name → (version, trailing text) for pinned lines."""
    found = {}
    for line in text.splitlines():
        if line.startswith((' ', '\t', '#')) or not line.strip():
            continue
        m = PIN_RE.match(line)
        if m:
            found[m.group('name').lower()] = (m.group('version'), m.group('rest'))
    return found


class PlatformPinTests(unittest.TestCase):
    """The macOS/Windows block must survive every regeneration."""

    def setUp(self):
        self.txt = _read(TXT_PATH)
        self.txt_pins = _pins(self.txt)

    def test_every_platform_dependency_is_pinned(self):
        for name in PLATFORM_PINS:
            with self.subTest(package=name):
                self.assertIn(
                    name, self.txt_pins,
                    f'{name} is missing from build-requirements.txt. A '
                    f'pip-compile run on a machine where its marker does not '
                    f'apply drops it, which breaks `pip install '
                    f'--require-hashes` on that OS. Restore the "Manual '
                    f'cross-platform pins" block.',
                )

    def test_each_carries_its_platform_marker(self):
        # Without the marker pip would try to install a Windows-only
        # package on Linux and fail the release build everywhere.
        for name, marker in PLATFORM_PINS.items():
            with self.subTest(package=name):
                _, rest = self.txt_pins[name]
                self.assertIn(marker, rest, f'{name} lost its {marker!r} marker')

    def test_declared_in_the_in_file_too(self):
        # The .in file is the source of truth a regenerator reads; if the
        # requirement only exists in generated output it reads as noise
        # and gets dropped.
        in_pins = _pins(_read(IN_PATH))
        for name in PLATFORM_PINS:
            with self.subTest(package=name):
                self.assertIn(name, in_pins, f'{name} is not declared in build-requirements.in')

    def test_in_and_txt_agree_on_versions(self):
        in_pins = _pins(_read(IN_PATH))
        for name, (version, _) in in_pins.items():
            with self.subTest(package=name):
                self.assertIn(name, self.txt_pins, f'{name} is in .in but not .txt')
                self.assertEqual(
                    self.txt_pins[name][0], version,
                    f'{name} is pinned to {version} in .in but '
                    f'{self.txt_pins[name][0]} in .txt',
                )


class HashPinningTests(unittest.TestCase):
    """--require-hashes needs every requirement to carry a hash."""

    def test_every_pinned_requirement_has_at_least_one_hash(self):
        text = _read(TXT_PATH)
        # Join continuation lines so each requirement is one record.
        records = text.replace('\\\n', ' ').splitlines()
        for line in records:
            if line.startswith((' ', '\t', '#')) or not line.strip():
                continue
            m = PIN_RE.match(line)
            if not m:
                continue
            with self.subTest(package=m.group('name')):
                self.assertIn(
                    '--hash=sha256:', line,
                    f'{m.group("name")} has no hash; release.yml installs with '
                    f'--require-hashes and would reject the whole file',
                )


if __name__ == '__main__':
    unittest.main()
