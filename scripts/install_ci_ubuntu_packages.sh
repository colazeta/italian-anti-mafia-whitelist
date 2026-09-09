#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "usage: $0 package [package ...]" >&2
  exit 2
fi

# GitHub-hosted Ubuntu images include third-party package sources that this
# repository does not depend on.  A transient Google Chrome metadata mismatch
# must not break unrelated validation workflows.
sudo find /etc/apt/sources.list.d -maxdepth 1 -type f \
  \( -iname '*chrome*.list' -o -iname '*chrome*.sources' -o -iname '*google-chrome*' \) \
  -print -delete || true

for attempt in 1 2 3; do
  sudo rm -rf /var/lib/apt/lists/*
  if sudo apt-get update -qq -o Acquire::Retries=3 && \
     sudo apt-get install -y --no-install-recommends "$@"; then
    exit 0
  fi
  if [ "$attempt" -eq 3 ]; then
    echo "Ubuntu package installation failed after bounded retries: $*" >&2
    exit 1
  fi
  sleep $((attempt * 3))
done
