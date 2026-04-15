#!/usr/bin/env bash
last=$(sz memory get heartbeat.last 2>/dev/null || echo "")
echo "last=$last"
exit 0
