# weatherbot
Post the current weather for a configured city to a local file every morning.

Goal: produce `posts/<date>.txt` once per day.

Run by hand:
    python -m weatherbot.post

Or let System Zero run it autonomously:
    sz init --yes
