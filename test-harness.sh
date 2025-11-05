#!/bin/bash
# test-harness.sh
#
# This script tests a single library against stable and nightly Node.js.
# It is designed to be called by the triage.py script.
#
# Arguments:
#   $1: The Git URL of the library (e.g., https://github.com/fastify/fastify.git)
#   $2: The short name of the library (e.g., fastify)

# Exit immediately if a command fails
set -e

GIT_URL=$1
LIB_NAME=$2
STABLE_EXIT_CODE=0
NIGHTLY_EXIT_CODE=0

# Clone the library
# --depth 1 is a shallow clone, which is much faster
git clone --depth 1 "$GIT_URL" "$LIB_NAME" > /dev/null 2>&1
cd "$LIB_NAME"

# --- Check if Testable ---
# Check 'package.json' for a "test" script.
# If it doesn't exist OR it's the default "Error: no test specified", mark as UNTESTABLE.
if ! grep -q "\"test\"" package.json || grep -q "\"Error: no test specified\"" package.json; then
  echo "{\"lib\": \"$LIB_NAME\", \"status\": \"UNTESTABLE\", \"stable_pass\": 1, \"nightly_pass\": 1, \"stable_log\": \"\", \"nightly_log\": \"\"}"
  
  # Cleanup
  cd ..
  rm -rf "$LIB_NAME"
  exit 0
fi

# --- Run Stable Test ---
# Create a temporary file for the log
STABLE_LOG_FILE=$(mktemp)
# Run the test inside the 'node-stable' container
# Mount the current directory ($(pwd)) into /app in the container
# We use '|| true' to prevent the script from exiting if the test fails. We want to capture the exit code.
docker run --rm -v "$(pwd)":/app -w /app node-stable sh -c "npm install --legacy-peer-deps && npm test" > $STABLE_LOG_FILE 2>&1 || true
STABLE_EXIT_CODE=$?
STABLE_LOG_B64=$(base64 -w 0 $STABLE_LOG_FILE)


# --- Run Nightly Test ---
NIGHTLY_LOG_FILE=$(mktemp)
docker run --rm -v "$(pwd)":/app -w /app node-nightly sh -c "npm install --legacy-peer-deps && npm test" > $NIGHTLY_LOG_FILE 2>&1 || true
NIGHTLY_EXIT_CODE=$?
NIGHTLY_LOG_B64=$(base64 -w 0 $NIGHTLY_LOG_FILE)


# --- Output JSON ---
# Print a single line of JSON to stdout, which will be captured by triage.py
echo "{\"lib\": \"$LIB_NAME\", \"status\": \"TESTED\", \"stable_pass\": $STABLE_EXIT_CODE, \"nightly_pass\": $NIGHTLY_EXIT_CODE, \"stable_log\": \"$STABLE_LOG_B64\", \"nightly_log\": \"$NIGHTLY_LOG_B64\"}"


# --- Cleanup ---
cd ..
sudo rm -rf "$LIB_NAME"
rm $STABLE_LOG_FILE $NIGHTLY_LOG_FILE
exit 0