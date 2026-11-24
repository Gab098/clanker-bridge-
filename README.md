# Clanker Bridge

A small, authenticated MCP server for a user-controlled Termux workspace.

## Current scope

- workspace_info: report server and workspace status.
- list_files: list one directory level inside the workspace.
- read_file: read UTF-8 text files (up to 1 MB).
- write_file: write UTF-8 text files (up to 1 MB).

There is deliberately no arbitrary shell or Python execution in this first version.
The server is restricted to one workspace directory.

## Install on Termux

~~~sh
pkg update
pkg install python git
git clone https://github.com/Gab098/clanker-bridge-.git
cd clanker-bridge-
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
mkdir -p "$HOME/clanker-workspace"
~~~

## Configure and start

Generate a fresh secret locally. Do not paste it into GitHub, chat, screenshots, or logs.

~~~sh
export CLANKER_BRIDGE_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export CLANKER_WORKSPACE="$HOME/clanker-workspace"
export CLANKER_HOST="127.0.0.1"
export CLANKER_PORT="8765"
python server.py
~~~

Keep the token in the Termux session or a private local environment file excluded
from Git. Anyone who obtains the token can read and modify files in the workspace.

## Network model

The server binds to loopback (127.0.0.1) by default. Do not bind it to
0.0.0.0 or expose the port directly to the public internet.

For private remote access, use a private Tailscale Serve configuration to proxy
the local port over your tailnet. Check the current Tailscale Serve syntax for
your installed version before enabling it. Keep tailnet access limited to devices
you trust. The bearer token remains required even behind Tailscale.

## Health check

From Termux:

~~~sh
curl http://127.0.0.1:8765/healthz
~~~

The MCP endpoint is /mcp and requires an Authorization: Bearer header containing
your local token.

## Security notes

- Never commit a real token or local .env file.
- Keep private workspace files out of this repository.
- Use a dedicated workspace; do not point it at $HOME.
- Review every file write before trusting a remote client.
- This version does not run shell commands or arbitrary scripts.
- Stop the server with Ctrl-C when it is not needed.
