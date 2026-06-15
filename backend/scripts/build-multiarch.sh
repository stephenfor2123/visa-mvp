#!/usr/bin/env bash
# scripts/build-multiarch.sh — build & push visa-mvp-backend to GHCR for both
# linux/amd64 (Intel/AMD servers, GitHub Actions, AWS x86) and linux/arm64
# (AWS Graviton, Apple Silicon via Docker Desktop, Raspberry Pi).
#
# Prereqs (run once):
#   1. Docker Desktop installed AND "Use containerd for pulling and storing images"
#      turned on (Settings → General → enable containerd image store).
#      This unlocks docker buildx for multi-arch without docker-container driver.
#   2. Logged in to GHCR:
#        echo "$GITHUB_TOKEN" | docker login ghcr.io -u stephen --password-stdin
#      (use a GitHub PAT with `write:packages` scope; keep in macOS keychain).
#   3. (One-time) create the buildx builder:
#        docker buildx create --use --name multiarch-builder \
#          --driver docker-container --bootstrap
#
# Usage:
#   ./scripts/build-multiarch.sh                # build + push :latest
#   ./scripts/build-multiarch.sh v0.2.0         # build + push :v0.2.0 + :latest
#   IMAGE_TAG=debug ./scripts/build-multiarch.sh # env override

set -euo pipefail

# ----- Config -------------------------------------------------------------
IMAGE_NAME="${IMAGE_NAME:-ghcr.io/stephen/visa-api}"
IMAGE_TAG="${1:-${IMAGE_TAG:-latest}}"
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"
BUILDER_NAME="${BUILDER_NAME:-multiarch-builder}"
DOCKERFILE="${DOCKERFILE:-Dockerfile}"
CONTEXT="${CONTEXT:-.}"
LOG_FILE="${LOG_FILE:-/tmp/docker-buildx-$(date +%Y%m%d-%H%M%S).log}"

# Resolve context to an absolute path so the script works from any CWD.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "$CONTEXT" in
  .) CONTEXT_ABS="$SCRIPT_DIR/.." ;;
  *) CONTEXT_ABS="$(cd "$CONTEXT" && pwd)" ;;
esac

echo "=========================================================="
echo " multi-arch build"
echo "   image:    ${IMAGE_NAME}:${IMAGE_TAG}"
echo "   platforms:${PLATFORMS}"
echo "   context:  ${CONTEXT_ABS}"
echo "   log:      ${LOG_FILE}"
echo "=========================================================="

# ----- Pre-flight ---------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker CLI not found. Install Docker Desktop first." >&2
  exit 1
fi

# Ensure builder exists; create it if missing.
if ! docker buildx inspect "$BUILDER_NAME" >/dev/null 2>&1; then
  echo "[setup] creating buildx builder '$BUILDER_NAME'..."
  docker buildx create --name "$BUILDER_NAME" \
    --driver docker-container --bootstrap
fi

docker buildx use "$BUILDER_NAME"

# ----- Build + push -------------------------------------------------------
# `--push` (not `--load`) is required for multi-arch: a single docker host can
# only `docker load` one architecture's manifest at a time.
docker buildx build \
  --platform "$PLATFORMS" \
  -f "$DOCKERFILE" \
  -t "${IMAGE_NAME}:${IMAGE_TAG}" \
  -t "${IMAGE_NAME}:latest" \
  --push \
  "$CONTEXT_ABS" 2>&1 | tee "$LOG_FILE"

echo
echo "=========================================================="
echo " DONE — pushed ${IMAGE_NAME}:${IMAGE_TAG} (and :latest)"
echo " log: $LOG_FILE"
echo "=========================================================="
