#!/bin/bash
# test-harness.sh
set -x # Enable debug tracing

# Arguments:
#   $1: The Git URL of the library
#   $2: The short name of the library

GIT_URL=$1
LIB_NAME=$2
STABLE_EXIT_CODE=0
NIGHTLY_EXIT_CODE=0

git clone --depth 1 "$GIT_URL" "$LIB_NAME" > /dev/null 2>&1
cd "$LIB_NAME"

# --- Check if Testable ---
if ! grep -q "\"test\"" package.json || grep -q "\"Error: no test specified\"" package.json; then
  echo "{\"lib\": \"$LIB_NAME\", \"status\": \"UNTESTABLE\", \"stable_pass\": 1, \"nightly_pass\": 1, \"stable_log\": \"\", \"nightly_log\": \"\"}"
  cd ..
  rm -rf "$LIB_NAME" || true
  exit 0
fi

# --- Run Stable Test ---
STABLE_LOG_FILE=$(mktemp)
# ADDED --build-from-source to force C++ compilation
docker run --rm -v "$(pwd)":/app -w /app node-stable sh -c "npm install --legacy-peer-deps --build-from-source && npm test" > $STABLE_LOG_FILE 2>&1 || true
STABLE_EXIT_CODE=$?
STABLE_LOG_B64=$(base64 -w 0 $STABLE_LOG_FILE)


# --- Run Nightly Test ---
NIGHTLY_LOG_FILE=$(mktemp)
# ADDED --build-from-source to force C++ compilation
docker run --rm -v "$(pwd)":/app -w /app node-nightly sh -c "npm install --legacy-peer-deps --build-from-source && npm test" > $NIGHTLY_LOG_FILE 2>&1 || true
NIGHTLY_EXIT_CODE=$?
NIGHTLY_LOG_B64=$(base64 -w 0 $NIGHTLY_LOG_FILE)


# --- Output JSON ---
echo "{\"lib\": \"$LIB_NAME\", \"status\": \"TESTED\", \"stable_pass\": $STABLE_EXIT_CODE, \"nightly_pass\": $NIGHTLY_EXIT_CODE, \"stable_log\": \"$STABLE_LOG_B64\", \"nightly_log\": \"$NIGHTLY_LOG_B64\"}"


# --- Cleanup ---
cd ..
sudo rm -rf "$LIB_NAME"
rm -f $STABLE_LOG_FILE $NIGHTLY_LOG_FILE || true
exit 0