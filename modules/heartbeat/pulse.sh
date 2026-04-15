#!/usr/bin/env bash
set -euo pipefail
sz bus emit pulse.tick "$(jq -nc --arg ts "$(date -u +%FT%TZ)" '{ts:$ts}')"
sz memory set heartbeat.last "$(date -u +%FT%TZ)"
