#!/usr/bin/env python3
"""Composio MCP klienta palīgs — runā ar connect.composio.dev/mcp tieši.

Lietošana:
    python3 composio_mcp.py search "post a tweet with image to X Twitter account"
    python3 composio_mcp.py call <tool_name> '<json_args>'
"""
import sys
import json
import requests

MCP_URL = "https://connect.composio.dev/mcp"


def get_key():
    import os
    k = os.environ.get("COMPOSIO_API_KEY")
    if k:
        return k.strip()
    for p in ("/root/.hermes/.env", "/root/scripts/.env"):
        try:
            for line in open(p, encoding="utf-8", errors="replace"):
                if line.strip().startswith("COMPOSIO_API_KEY="):
                    return line.strip().split("=", 1)[1].strip().strip('"').strip("'")
        except FileNotFoundError:
            pass
    raise RuntimeError("COMPOSIO_API_KEY nav atrasts")


def rpc(method, params, key, req_id=1):
    payload = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params,
    }
    r = requests.post(
        MCP_URL,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        json=payload,
        timeout=60,
    )
    r.raise_for_status()
    # SSE formāts: "event: message\ndata: {...}"
    text = r.text
    # izvelc pēdējo data: rindiņu
    data_lines = [l[6:] for l in text.splitlines() if l.startswith("data: ")]
    if not data_lines:
        return json.loads(text)
    return json.loads(data_lines[-1])


def main():
    key = get_key()
    cmd = sys.argv[1]
    if cmd == "search":
        use_case = sys.argv[2]
        res = rpc("tools/call", {
            "name": "COMPOSIO_SEARCH_TOOLS",
            "arguments": {
                "queries": [{"use_case": use_case}],
                "session": {"generate_id": True},
            },
        }, key)
        print(json.dumps(res, indent=2)[:3000])
    elif cmd == "call":
        tool = sys.argv[2]
        args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        res = rpc("tools/call", {"name": tool, "arguments": args}, key)
        print(json.dumps(res, indent=2)[:3000])
    else:
        print("nezināma komanda")


if __name__ == "__main__":
    main()
