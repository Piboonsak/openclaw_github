import os
import sys


def verify_evidence():
    print("=== AI Dev Gate: Evidence Verification ===")
    evidence_dir = ".agent/evidence"
    if not os.path.exists(evidence_dir):
        print("🚨 ERROR: .agent/evidence/ directory does not exist.")
        sys.exit(1)

    evidence_files = [
        f
        for f in os.listdir(evidence_dir)
        if f.endswith(".md") or f.endswith(".txt")
    ]
    # Filter out git keeps
    evidence_files = [f for f in evidence_files if f != ".gitkeep"]

    if not evidence_files:
        print("🚨 ERROR: No test evidence file found in .agent/evidence/.")
        print(
            "Please save your test execution stdout logs to '.agent/evidence/TASK-ID.md'"
        )
        sys.exit(1)

    for fname in evidence_files:
        path = os.path.join(evidence_dir, fname)
        size = os.path.getsize(path)
        if size < 50:
            print(
                f"🚨 ERROR: Evidence file '{fname}' is empty or too short ({size} bytes)."
            )
            sys.exit(1)

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            # Look for standard pytest or testing execution markers
            if "test" not in content.lower() and "pass" not in content.lower():
                print(
                    f"🚨 ERROR: Evidence '{fname}' lacks genuine execution markers ('test' or 'pass')."
                )
                sys.exit(1)

    print("✅ Success: Test evidence approved and authenticated.")
    sys.exit(0)


if __name__ == "__main__":
    verify_evidence()
