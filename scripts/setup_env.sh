#!/usr/bin/env bash
# One-time setup: download micromamba and create the project-local env (Python + PostgreSQL + packages).
set -euo pipefail
source "$(dirname "$0")/env.sh"

if [ ! -x "$MICROMAMBA" ]; then
  mkdir -p "$PROJECT_ROOT/.tools"
  case "$(uname -s)-$(uname -m)" in
    Darwin-arm64)  PLATFORM=osx-arm64 ;;
    Darwin-x86_64) PLATFORM=osx-64 ;;
    Linux-x86_64)  PLATFORM=linux-64 ;;
    Linux-aarch64) PLATFORM=linux-aarch64 ;;
    *) echo "Unsupported platform"; exit 1 ;;
  esac
  echo "Downloading micromamba ($PLATFORM)..."
  curl -Ls "https://micro.mamba.pm/api/micromamba/$PLATFORM/latest" | tar -xj -C "$PROJECT_ROOT/.tools" --strip-components=1 bin/micromamba
fi

if [ ! -d "$ENV_PREFIX" ]; then
  "$MICROMAMBA" create -y -p "$ENV_PREFIX" -f "$PROJECT_ROOT/environment.yml"
else
  "$MICROMAMBA" install -y -p "$ENV_PREFIX" -f "$PROJECT_ROOT/environment.yml"
fi
echo "Environment ready at $ENV_PREFIX"
