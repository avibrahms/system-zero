#!/usr/bin/env bash
([ -d "${SZ_REPO_ROOT:-$(pwd)}/core/system" ] && [ -f "${SZ_REPO_ROOT:-$(pwd)}/core/system/maintenance-registry.yaml" ]) && echo "connection_engine" || exit 1
