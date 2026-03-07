#!/usr/bin/env bash
# scripts/workflow-logging.sh
# Shared logging utilities for GitHub Actions workflows
# 
# Usage in workflows:
#   source scripts/workflow-logging.sh
#   create_deploy_log_dir
#   log_to_deploy "message"
#   log_deploy_diagnostic "command output"

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────

# Get or set deployment run number (GitHub Actions: $GITHUB_RUN_NUMBER)
DEPLOY_RUN_NUMBER="${GITHUB_RUN_NUMBER:-$(date +%s)}"
DEPLOY_LOG_BASE="operations/deployments/deploy-${DEPLOY_RUN_NUMBER}"
DEPLOY_LOG_DIR="${DEPLOY_LOG_BASE}/logs"

BUILD_RUN_NUMBER="${GITHUB_RUN_NUMBER:-$(date +%s)}"
BUILD_LOG_DIR="operations/builds/build-${BUILD_RUN_NUMBER}"

# ── Functions ─────────────────────────────────────────────────────────────────

# Create deployment log directory and write metadata
create_deploy_log_dir() {
    mkdir -p "$DEPLOY_LOG_DIR"
    
    cat > "${DEPLOY_LOG_DIR}/metadata.json" << METADATA
{
  "run_id": "${GITHUB_RUN_ID:-unknown}",
  "run_number": ${GITHUB_RUN_NUMBER:-0},
  "branch": "${GITHUB_REF:-unknown}",
  "commit_sha": "${GITHUB_SHA:-unknown}",
  "commit_message": "${GITHUB_EVENT_HEAD_COMMIT_MESSAGE:-}",
  "timestamp": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "workflow_file": "${GITHUB_WORKFLOW:-unknown}",
  "repository": "${GITHUB_REPOSITORY:-unknown}",
  "actor": "${GITHUB_ACTOR:-unknown}"
}
METADATA
    
    echo "✓ Created deployment log directory: $DEPLOY_LOG_DIR"
}

# Log message to deployment output file
log_to_deploy() {
    local message="$1"
    mkdir -p "$DEPLOY_LOG_DIR"
    echo "[$(date -u +'%Y-%m-%d %H:%M:%S UTC')] $message" >> "${DEPLOY_LOG_DIR}/deploy.log"
}

# Capture command output to deployment logs
log_deploy_command() {
    local name="$1"
    local command="$2"
    local output_file="${DEPLOY_LOG_DIR}/${name}.txt"
    
    mkdir -p "$DEPLOY_LOG_DIR"
    echo "Executing: $command" > "$output_file"
    echo "---" >> "$output_file"
    
    if eval "$command" >> "$output_file" 2>&1; then
        echo "✓ Logged: $output_file"
        return 0
    else
        echo "✗ Command failed (output in $output_file)" >&2
        return 1
    fi
}

# Capture diagnostic information
log_deploy_diagnostics() {
    mkdir -p "$DEPLOY_LOG_DIR"
    
    {
        echo "=== Deployed Image Tag ==="
        echo "${IMAGE_TAG:-unknown}"
        echo ""
        echo "=== Workflow Metadata ==="
        echo "Run ID: ${GITHUB_RUN_ID:-unknown}"
        echo "Run Number: ${GITHUB_RUN_NUMBER:-unknown}"
        echo "Branch: ${GITHUB_REF:-unknown}"
        echo "Commit: ${GITHUB_SHA:-unknown}"
        echo "Timestamp: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
        echo ""
        echo "=== Environment ==="
        echo "Node: $(node -v 2>/dev/null || echo 'not installed')"
        echo "Bash: $(bash --version 2>/dev/null | head -1)"
        echo "Docker: $(docker --version 2>/dev/null || echo 'not installed')"
    } > "${DEPLOY_LOG_DIR}/environment.txt"
}

# Create build log directory
create_build_log_dir() {
    mkdir -p "$BUILD_LOG_DIR"
    
    cat > "${BUILD_LOG_DIR}/metadata.json" << METADATA
{
  "build_number": ${GITHUB_RUN_NUMBER:-0},
  "run_id": "${GITHUB_RUN_ID:-unknown}",
  "branch": "${GITHUB_REF:-unknown}",
  "commit_sha": "${GITHUB_SHA:-unknown}",
  "timestamp": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "workflow_file": "${GITHUB_WORKFLOW:-unknown}",
  "status": "started"
}
METADATA
    
    echo "✓ Created build log directory: $BUILD_LOG_DIR"
}

# Log build image digest
log_build_image_digest() {
    local digest="$1"
    mkdir -p "$BUILD_LOG_DIR"
    echo "$digest" > "${BUILD_LOG_DIR}/image-digest.txt"
    echo "✓ Logged image digest: $digest"
}

# Export functions and variables for subshells
export -f create_deploy_log_dir
export -f log_to_deploy
export -f log_deploy_command
export -f log_deploy_diagnostics
export -f create_build_log_dir
export -f log_build_image_digest
export DEPLOY_RUN_NUMBER DEPLOY_LOG_DIR BUILD_RUN_NUMBER BUILD_LOG_DIR

# Print summary
if [[ "${1:-}" == "--info" ]]; then
    echo "📋 Workflow Logging Configuration:"
    echo ""
    echo "Deploy logs:  $DEPLOY_LOG_DIR"
    echo "Build logs:   $BUILD_LOG_DIR"
    echo ""
    echo "Available functions:"
    echo "  create_deploy_log_dir              # Create and initialize deploy log dir"
    echo "  log_to_deploy <message>            # Append message to deploy.log"
    echo "  log_deploy_command <name> <cmd>    # Execute and capture command output"
    echo "  log_deploy_diagnostics             # Save environment/config info"
    echo "  create_build_log_dir                # Create and initialize build log dir"
    echo "  log_build_image_digest <digest>    # Save Docker image digest"
    echo ""
    echo "Export variables:"
    echo "  \$DEPLOY_LOG_DIR    = $DEPLOY_LOG_DIR"
    echo "  \$BUILD_LOG_DIR     = $BUILD_LOG_DIR"
fi
