#!/bin/bash
# Build the dashboard, then do a clean cutover on Modal. The web function runs on a single
# container that holds dashboard websockets, so a rolling deploy would wait for those sockets
# to time out (up to 10 min). Stopping first swaps versions in about 30 seconds.
set -euo pipefail
cd "$(dirname "$0")"
(cd ../dashboard && npm run build >/dev/null)
modal app stop -y govmind 2>/dev/null || true
modal deploy modal_app.py
