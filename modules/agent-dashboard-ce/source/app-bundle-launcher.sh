#!/bin/bash

set -euo pipefail

REPO_LINK="$HOME/.agent-dashboard/current-repo"
REQUIRED_SCRIPT="modules/agent-dashboard/launch-dashboards-app.sh"

is_valid_repo() {
    local root="${1:-}"
    [[ -n "$root" && -d "$root/.git" && -x "$root/$REQUIRED_SCRIPT" ]]
}

cache_repo_root() {
    local root=$1
    mkdir -p "$(dirname "$REPO_LINK")"
    ln -sfn "$root" "$REPO_LINK"
}

repo_root_from_script() {
    local script_path="${1:-}"
    local root

    [[ -n "$script_path" && -f "$script_path" ]] || return 1
    root="$(cd "$(dirname "$script_path")/../.." && pwd -P)" || return 1
    is_valid_repo "$root" || return 1
    printf '%s\n' "$root"
}

candidate_roots() {
    if [[ -n "${CONNECTION_ENGINE_ROOT:-}" ]]; then
        printf '%s\n' "$CONNECTION_ENGINE_ROOT"
    fi

    if [[ -L "$REPO_LINK" ]]; then
        readlink "$REPO_LINK"
    elif [[ -d "$REPO_LINK" ]]; then
        printf '%s\n' "$REPO_LINK"
    fi

    printf '%s\n' \
        "$HOME/Documents/Misc/connection-engine" \
        "$HOME/Documents/connection-engine" \
        "$HOME/Projects/connection-engine" \
        "$HOME/Code/connection-engine" \
        "$HOME/Desktop/connection-engine"
}

search_repo_root() {
    local candidate
    local resolved
    local match
    local base

    while IFS= read -r candidate; do
        [[ -n "$candidate" ]] || continue
        if is_valid_repo "$candidate"; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done < <(candidate_roots)

    if command -v mdfind >/dev/null 2>&1; then
        while IFS= read -r match; do
            [[ "$match" == */modules/agent-dashboard/launch-dashboards-app.sh ]] || continue
            [[ "$match" == *"/archived/"* || "$match" == *"/.Trash/"* ]] && continue
            if resolved="$(repo_root_from_script "$match")"; then
                printf '%s\n' "$resolved"
                return 0
            fi
        done < <(mdfind "kMDItemFSName == 'launch-dashboards-app.sh'" 2>/dev/null || true)
    fi

    for base in "$HOME/Documents" "$HOME/Desktop" "$HOME/Projects" "$HOME/Code" "$HOME"; do
        [[ -d "$base" ]] || continue
        while IFS= read -r match; do
            [[ "$match" == *"/archived/"* || "$match" == *"/.Trash/"* ]] && continue
            if resolved="$(repo_root_from_script "$match")"; then
                printf '%s\n' "$resolved"
                return 0
            fi
        done < <(find "$base" -maxdepth 6 -path "*/modules/agent-dashboard/launch-dashboards-app.sh" -type f 2>/dev/null)
    done

    return 1
}

main() {
    local repo_root

    repo_root="$(search_repo_root)" || {
        osascript -e 'display alert "Connection Engine Dashboards" message "Could not locate the connection-engine repo. Re-run modules/agent-dashboard/install.sh from the repo root." as critical' >/dev/null 2>&1 || true
        echo "Connection Engine Dashboards: could not locate a valid connection-engine repo" >&2
        exit 1
    }

    cache_repo_root "$repo_root"
    exec "$repo_root/$REQUIRED_SCRIPT" "$@"
}

main "$@"
