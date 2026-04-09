#!/usr/bin/env bash
#
# Local validator for Incident Bridge hackathon submissions.
#
# Checks:
#   1. The running OpenEnv server responds to POST /reset
#   2. The Docker image builds from this repo
#   3. `openenv validate` passes locally
#
# Usage:
#   ./scripts/validate-submission.sh <base_url> [repo_dir]
#

set -uo pipefail

DOCKER_BUILD_TIMEOUT=600

if [ -t 1 ]; then
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  BOLD='\033[1m'
  NC='\033[0m'
else
  RED='' GREEN='' YELLOW='' BOLD='' NC=''
fi

run_with_timeout() {
  local secs="$1"
  shift

  if command -v timeout >/dev/null 2>&1; then
    timeout "$secs" "$@"
  elif command -v gtimeout >/dev/null 2>&1; then
    gtimeout "$secs" "$@"
  else
    "$@" &
    local pid=$!
    ( sleep "$secs" && kill "$pid" 2>/dev/null ) &
    local watcher=$!
    wait "$pid" 2>/dev/null
    local rc=$?
    kill "$watcher" 2>/dev/null
    wait "$watcher" 2>/dev/null || true
    return $rc
  fi
}

BASE_URL="${1:-}"
REPO_DIR="${2:-.}"

if [ -z "$BASE_URL" ]; then
  printf "Usage: %s <base_url> [repo_dir]\n" "$0"
  exit 1
fi

if ! REPO_DIR="$(cd "$REPO_DIR" 2>/dev/null && pwd)"; then
  printf "Error: directory '%s' not found\n" "${2:-.}"
  exit 1
fi

BASE_URL="${BASE_URL%/}"

log()  { printf "[%s] %b\n" "$(date -u +%H:%M:%S)" "$*"; }
pass() { log "${GREEN}PASSED${NC} -- $1"; }
fail() { log "${RED}FAILED${NC} -- $1"; }
hint() { printf "  ${YELLOW}Hint:${NC} %b\n" "$1"; }

printf "\n"
printf "${BOLD}========================================${NC}\n"
printf "${BOLD}  Incident Bridge Submission Validator${NC}\n"
printf "${BOLD}========================================${NC}\n"
log "Repo:     $REPO_DIR"
log "Base URL: $BASE_URL"
printf "\n"

log "${BOLD}Step 1/3: Pinging /reset${NC}"
HTTP_CODE="$(curl -s -o /tmp/incident-bridge-reset.out -w "%{http_code}" -X POST \
  -H "Content-Type: application/json" \
  -d '{}' \
  "$BASE_URL/reset" \
  --max-time 30 || printf '000')"

if [ "$HTTP_CODE" = "200" ]; then
  pass "Running environment responds to POST /reset"
else
  fail "POST /reset returned HTTP $HTTP_CODE"
  hint "Run 'uv run server --port 8000' or deploy the Space before validating."
  exit 1
fi

log "${BOLD}Step 2/3: Building Docker image${NC}"
if ! command -v docker >/dev/null 2>&1; then
  fail "docker command not found"
  hint "Install Docker Desktop before running this validator."
  exit 1
fi

BUILD_OUTPUT="$(cd "$REPO_DIR" && run_with_timeout "$DOCKER_BUILD_TIMEOUT" \
  docker build -t incident-bridge-env:latest -f server/Dockerfile . 2>&1)"
BUILD_STATUS=$?
if [ "$BUILD_STATUS" -eq 0 ]; then
  pass "Docker build succeeded"
else
  fail "Docker build failed"
  printf "%s\n" "$BUILD_OUTPUT" | tail -20
  exit 1
fi

log "${BOLD}Step 3/3: Running openenv validate${NC}"
if command -v openenv >/dev/null 2>&1; then
  VALIDATE_CMD=(openenv validate .)
elif [ -x "$REPO_DIR/.venv/bin/openenv" ]; then
  VALIDATE_CMD=("$REPO_DIR/.venv/bin/openenv" validate .)
elif command -v uv >/dev/null 2>&1; then
  VALIDATE_CMD=(uv run openenv validate .)
else
  fail "openenv command not found"
  hint "Install dependencies with 'uv sync --dev' or activate the project virtualenv."
  exit 1
fi

VALIDATE_OUTPUT="$(cd "$REPO_DIR" && "${VALIDATE_CMD[@]}" 2>&1)"
VALIDATE_STATUS=$?
if [ "$VALIDATE_STATUS" -eq 0 ]; then
  pass "openenv validate passed"
  [ -n "$VALIDATE_OUTPUT" ] && printf "%s\n" "$VALIDATE_OUTPUT"
else
  fail "openenv validate failed"
  printf "%s\n" "$VALIDATE_OUTPUT"
  exit 1
fi

printf "\n"
printf "${BOLD}========================================${NC}\n"
printf "${GREEN}${BOLD}  All checks passed.${NC}\n"
printf "${GREEN}${BOLD}  This repo is ready for submission testing.${NC}\n"
printf "${BOLD}========================================${NC}\n"
printf "\n"
