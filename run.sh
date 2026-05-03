#!/bin/sh
set -eu

cd /app

# Run immediately on start, then every 4 hours.
while true; do
	if ! python -m src.main; then
		echo "log-patrol run failed; retrying in 300s" >&2
		sleep 300
		continue
	fi
	sleep 14400
done
