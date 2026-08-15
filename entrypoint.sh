#!/bin/sh
set -e

if [ -n "$MYNTRA_COOKIES_JSON" ]; then
  printf '%s' "$MYNTRA_COOKIES_JSON" > /app/myntra_cookies.json
fi

Xvfb :99 -screen 0 1280x1024x24 -nolisten tcp &
export DISPLAY=:99

for i in $(seq 1 20); do
  [ -e /tmp/.X11-unix/X99 ] && break
  sleep 0.5
done

exec python myntra_weekly_order.py
