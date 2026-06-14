"""tests/test_no_dark_skipped_files.py — meta-guard against silently dark-skipped
test files.

THE FOOTGUN THIS CATCHES (real incident, Sprint WEXP activity):
  A MODULE-SCOPE ``pytest.importorskip("requests")`` (an EXTERNAL package that
  wasn't installed) raised ``Skipped`` at IMPORT time, which makes pytest skip the
  ENTIRE module. ~37 real tests in test_activity.py silently vanished every run —
  ``pytest test_activity.py --co`` printed "no tests collected" — and coverage on
  the service sat at 19% while the summary line just said "skipped" (looks benign).

  A whole test file going dark is invisible in the normal summary: skips don't fail
  CI, and a missing file's tests simply aren't there to be counted. This guard makes
  that condition LOUD.

HOW: collect (``--collect-only``, no execution) the whole tests/ dir in a fresh
subprocess, map which files produced ≥1 test node, then assert EVERY ``test_*.py``
on disk produced at least one node. A file that collects zero = dark-skipped.

WHY a subprocess (not the in-process pytest API): collecting from inside a running
collection is fragile/re-entrant. A clean ``--collect-only`` child is the same thing
CI would run, and it's one fast call (no test bodies execute).

DISTINGUISHING-CASE PROOF (manually verified when this guard was written, see the
end_sprint note): dropping a file with a module-scope ``importorskip`` on a
guaranteed-absent package makes THIS test FAIL naming that file; removing the file
makes it pass again. So the guard genuinely discriminates dark from healthy — it is
not an always-green stub.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
# This guard file is allowed to be excluded from its own check (it always has tests,
# but listing it keeps the intent explicit if it were ever parametrised away).
_SELF = Path(__file__).name


def _all_test_files() -> set[str]:
    """Every ``test_*.py`` file in tests/ (the files pytest would try to collect)."""
    return {p.name for p in TESTS_DIR.glob("test_*.py")}


def _files_that_collected_at_least_one_test() -> set[str]:
    """Run ``pytest --collect-only`` over tests/ in a subprocess and return the set of
    file basenames that produced at least one collected node id.

    Node ids look like ``tests/test_x.py::test_fn`` (or ``...::Class::test_fn``)."""
    proc = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            str(TESTS_DIR),
            "--collect-only", "-q",
            "-p", "no:cacheprovider",
            # keep the child light + deterministic: no coverage plugin, no ini addopts
            "-p", "no:cov",
        ],
        capture_output=True,
        text=True,
        cwd=str(TESTS_DIR.parent),  # backend/ — so pythonpath="." resolves modules.*
    )
    collected: set[str] = set()
    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if "::" not in line:
            continue
        # node id forms: 'tests/test_x.py::...' or 'test_x.py::...'
        node_path = line.split("::", 1)[0]
        name = Path(node_path).name
        if name.endswith(".py"):
            collected.add(name)
    return collected, proc


def test_no_test_file_collects_zero_tests():
    """Every test_*.py file must contribute ≥1 collected test. A file that collects
    zero is DARK-SKIPPED (e.g. a module-scope importorskip on a missing external
    package) — its tests silently don't run. Fail loudly, naming the offenders."""
    on_disk = _all_test_files()
    collected, proc = _files_that_collected_at_least_one_test()

    # Sanity: the collection subprocess itself must have succeeded (exit 0 or 5=no-tests
    # would itself be a red flag). pytest exit 0 = collected ok.
    assert proc.returncode == 0, (
        "collection subprocess failed — cannot verify dark-skip state.\n"
        f"returncode={proc.returncode}\n"
        f"STDOUT tail:\n{proc.stdout[-2000:]}\n"
        f"STDERR tail:\n{proc.stderr[-2000:]}"
    )

    dark = sorted(on_disk - collected - {_SELF})
    assert not dark, (
        "Dark-skipped test file(s) — they collect ZERO tests, so their tests "
        "silently never run (the activity/importorskip footgun):\n  "
        + "\n  ".join(dark)
        + "\n\nLikely cause: a MODULE-SCOPE `pytest.importorskip(...)` on a package "
        "that isn't installed, which skips the whole module at import time. Move the "
        "import into a fixture or guard only the section that needs it (see "
        "test_activity.py Section B for the fix pattern)."
    )


def test_guard_sees_all_known_test_files():
    """Self-check: the guard actually found the test files on disk (so a globbing bug
    can't make test_no_test_file_collects_zero_tests vacuously pass)."""
    on_disk = _all_test_files()
    # There are dozens of test files; a tiny number means the glob broke.
    assert len(on_disk) >= 10, f"expected many test_*.py files, found {len(on_disk)}: {on_disk}"
    assert _SELF in on_disk  # this file is itself discoverable
