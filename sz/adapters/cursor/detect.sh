#!/usr/bin/env bash
([ -f "${SZ_REPO_ROOT:-$(pwd)}/.cursorrules" ] || [ -d "${SZ_REPO_ROOT:-$(pwd)}/.cursor" ]) && echo "cursor" || exit 1
