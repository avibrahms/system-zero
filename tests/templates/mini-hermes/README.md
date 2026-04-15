# mini-hermes

A tiny dynamic repo. It already has an autonomous loop in `bin/mini-hermes.sh`. The loop appends a line to `pulse.log` every 5 seconds.

Goal: keep `pulse.log` growing as long as the daemon runs.

If you install System Zero into this repo, it must NOT start a competing daemon. It must adopt this one.
