#!/usr/bin/env bash
[ -f "${SZ_REPO_ROOT:-$(pwd)}/.hermes/config.yaml" ] && echo "hermes" || exit 1
