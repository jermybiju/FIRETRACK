
"""Safely restore the published FIRETRACK database release."""

import gzip
import hashlib
import os
import shutil
import sqlite3
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

URL = (
    "https://github.com/jermybiju/FIRETRACK/"
    "releases/download/data-v1/firetrack.db.gz"
)

EXPECTED_SHA256 = (
    "b1d38368823f0d036d507c0252330fdf"
    "760c0b4b232238bba5fff43ef839673d"
)

EXPECTED_ROWS = 1_220_961


def main():
    data_dir = Path(
        os.environ.get("FIRETRACK_DATA_DIR", ROOT / "data")
    )
    target = Path(
        os.environ.get("FIRETRACK_DB", data_dir / "firetrack.db")
    )

    target.parent.mkdir(parents=True, exist_ok=True)

    # Never overwrite an existing database.
    if target.exists():
        print(f"[RESTORE] Database already exists: {target}")
        print("[RESTORE] Refusing to overwrite it.")
        return

    compressed = None
    restored = None

    try:
        fd, compressed_name = tempfile.mkstemp(
            dir=target.parent, suffix=".db.gz"
        )
        os.close(fd)
        compressed = Path(compressed_name)

        print("[RESTORE] Downloading GitHub Release...")
        request = urllib.request.Request(
            URL, headers={"User-Agent": "FIRETRACK-Database-Restore"}
        )

        digest = hashlib.sha256()

        with urllib.request.urlopen(request, timeout=120) as response:
            with compressed.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    output.write(chunk)

        actual_sha = digest.hexdigest()
        if actual_sha != EXPECTED_SHA256:
            raise RuntimeError("SHA-256 verification failed")

        print("[RESTORE] SHA-256 verified.")

        fd, restored_name = tempfile.mkstemp(
            dir=target.parent, suffix=".db"
        )
        os.close(fd)
        restored = Path(restored_name)

        print("[RESTORE] Extracting database...")
        with gzip.open(compressed, "rb") as source:
            with restored.open("wb") as output:
                shutil.copyfileobj(source, output)

        print("[RESTORE] Checking SQLite integrity...")
        connection = sqlite3.connect(str(restored))
        try:
            integrity = connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]
            rows = connection.execute(
                "SELECT COUNT(*) FROM detections"
            ).fetchone()[0]
        finally:
            connection.close()

        if integrity != "ok":
            raise RuntimeError("SQLite integrity check failed")

        if rows != EXPECTED_ROWS:
            raise RuntimeError(
                f"Unexpected detection count: {rows}"
            )

        # Atomic placement: only after all checks pass.
        os.replace(restored, target)
        restored = None

        print("[RESTORE] SUCCESS")
        print(f"[RESTORE] Records: {rows:,}")
        print(f"[RESTORE] Database: {target}")

    finally:
        if compressed and compressed.exists():
            compressed.unlink()
        if restored and restored.exists():
            restored.unlink()


if __name__ == "__main__":
    main()
