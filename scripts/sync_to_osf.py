"""
sync_to_osf.py — Upload key project outputs to OSF node hqavj.

Triggered automatically by .git/hooks/post-push.
Can also be run manually: python scripts/sync_to_osf.py

Uses curl subprocess for all PUT requests (Tulane proxy intercepts SSL;
Python requests fails on PUT to files.osf.io).
"""

import os
import subprocess
import sys
from pathlib import Path

NODE_ID   = "hqavj"
OSF_TOKEN = os.environ.get("OSF_TOKEN", "")
BASE_URL  = f"https://files.osf.io/v1/resources/{NODE_ID}/providers/osfstorage"
BASE_DIR  = Path(__file__).parent.parent

# Files to sync: (local_path_relative_to_project, osf_filename)
# Keep this list focused on research outputs and replication materials.
SYNC_FILES = [
    # Paper outputs
    ("paper/overconfidence_pnas.pdf",  "overconfidence_pnas.pdf"),
    ("paper/overconfidence_ms.pdf",    "overconfidence_ms.pdf"),
    # Documentation
    ("CLAUDE.md",                      "CLAUDE.md"),
    ("STATE.md",                       "STATE.md"),
    ("study4/README.md",               "study4_README.md"),
    # Study configs (replication)
    ("study2/config.yaml",             "study2_config.yaml"),
    ("study3/config.yaml",             "study3_config.yaml"),
    ("study4/config.yaml",             "study4_config.yaml"),
    # Scored data (primary research outputs)
    ("study1/results/scored.csv",      "study1_scored.csv"),
    ("study1/results/summary.csv",     "study1_summary.csv"),
    ("study2/data/results/scored.csv", "study2_scored.csv"),
    ("study2/data/results/summary.csv","study2_summary.csv"),
    ("study3/data/results/scored.csv", "study3_scored.csv"),
    ("study3/data/results/summary.csv","study3_summary.csv"),
]


def upload(local_rel: str, osf_name: str) -> bool:
    local_path = BASE_DIR / local_rel
    if not local_path.exists():
        print(f"  SKIP  {local_rel} (not found)")
        return True

    url = f"{BASE_URL}/?kind=file&name={osf_name}"
    cmd = [
        "curl", "--insecure", "-s", "-o", "/dev/null", "-w", "%{http_code}",
        "-X", "PUT",
        "-H", f"Authorization: Bearer {OSF_TOKEN}",
        "--data-binary", f"@{local_path}",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    status = result.stdout.strip()
    ok = status in ("200", "201")
    icon = "OK  " if ok else "FAIL"
    print(f"  {icon}  {local_rel} -> osf.io/{NODE_ID} ({status})")
    return ok


def main():
    if not OSF_TOKEN:
        print("[sync_to_osf] OSF_TOKEN not set — skipping sync.")
        sys.exit(0)

    print(f"[sync_to_osf] Syncing to osf.io/{NODE_ID}...")
    failures = 0
    for local_rel, osf_name in SYNC_FILES:
        if not upload(local_rel, osf_name):
            failures += 1

    if failures:
        print(f"[sync_to_osf] {failures} upload(s) failed.")
    else:
        print(f"[sync_to_osf] Done.")


if __name__ == "__main__":
    main()
