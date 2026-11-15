"""Run the FIRETRACK test suite.

    python run_tests.py            # everything
    python run_tests.py -v         # verbose

The suite uses synthetic fixtures only (clearly labelled `test_synthetic` inside
the throw-away database) plus small inline CSV strings. It never touches the
application database.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "tests"))


def main() -> int:
    verbosity = 2 if "-v" in sys.argv or "--verbose" in sys.argv else 1
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "backend" / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    print()
    print(f"Ran {result.testsRun} tests")
    if result.skipped:
        print(f"Skipped: {len(result.skipped)}")
    if result.failures or result.errors:
        print(f"FAILURES: {len(result.failures)}  ERRORS: {len(result.errors)}")
        return 1
    print("All tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
