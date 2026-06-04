#!/bin/bash
# check_scope.sh — Ensure agent does not modify code outside allowed boundaries

set -e

echo "=== AI Dev Gate: Scope Compliance Check ==="

# Changed files list on current branch relative to default branch
CHANGED_FILES=$(git diff --name-only origin/main...HEAD || git diff --name-only main)

echo "Files changed on this branch:"
echo "$CHANGED_FILES"

# Check each modified file
for file in $CHANGED_FILES; do
    # Ignore configuration, environments, tests, documentation, and tooling
    if [[ $file =~ ^docs/ || $file =~ ^tests/ || $file =~ ^scripts/ || $file =~ ^\.github/ || $file =~ ^config/ || $file == ".gitignore" || $file == ".gitattributes" || $file == "requirements.txt" || $file == "package.json" || $file =~ ^private_data/ ]]; then
        continue
    fi
    
    # Ensure code modifications remain confined to the src/ module
    if [[ ! $file =~ ^src/ ]]; then
        echo "🚨 ERROR: File '$file' is modified outside allowed scope 'src/'."
        exit 1
    fi
done

echo "✅ Success: All modified files are within allowed boundaries."
exit 0
