import os
import subprocess
import sys

# High security risk pattern markers
HIGH_RISK_PATTERNS = [
    "docker/nginx/openclaw.conf",
    "docker/docker-compose.dev.yml",
    "requirements.txt",
    "setup.py",
    ".gitattributes",
]

# Medium risk pattern markers
MEDIUM_RISK_PATTERNS = [
    "src/api/endpoints.py",
    "src/config/settings.py",
    "src/ocr/processor.py",
]


def get_risk_tier():
    print("=== AI Dev Gate: High-Dependency Risk Classifier ===")
    try:
        changed_files = subprocess.check_output(
            ["git", "diff", "--name-only", "origin/main...HEAD"], text=True
        ).splitlines()
    except Exception:
        # Local fallback
        try:
            changed_files = subprocess.check_output(
                ["git", "diff", "--name-only", "main"], text=True
            ).splitlines()
        except Exception:
            changed_files = []

    if not changed_files:
        print("Risk Tier: LOW (No changed files detected)")
        return "LOW"

    highest_risk = "LOW"
    for file in changed_files:
        if any(marker in file for marker in HIGH_RISK_PATTERNS):
            highest_risk = "HIGH"
            break
        elif any(marker in file for marker in MEDIUM_RISK_PATTERNS):
            highest_risk = "MEDIUM"

    print(f"Calculated Risk Tier: {highest_risk}")

    # Bind output to GHA workflow steps if running inside GHA runner
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"risk_tier={highest_risk}\n")

    return highest_risk


if __name__ == "__main__":
    get_risk_tier()
