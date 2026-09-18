#!/usr/bin/env python3
"""X posta nosūtīšana caur composio MCP tieši no VPS (bez MacBook).

Plūsma:
1. Servē bildi no VPS (http.server 8123) — vai ņem jau esošu.
2. COMPOSIO_REMOTE_WORKBENCH: lejupielādē bildi sandboxā + upload_local_file → s3key.
3. TWITTER_UPLOAD_MEDIA ar s3key → media_id.
4. TWITTER_CREATION_OF_A_POST ar text + media_media_ids.

Lietošana:
    python3 composio_x_post.py '<post_text>' <image_path>
"""
import sys
import json
import time
import requests
import subprocess
import os

MCP_URL = "https://connect.composio.dev/mcp"
SESSION_ID = "wash"


def get_key():
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


def rpc(method, params, key, req_id=1, timeout=180):
    r = requests.post(
        MCP_URL,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        json={"jsonrpc": "2.0", "id": req_id, "method": method, "params": params},
        timeout=timeout,
    )
    r.raise_for_status()
    text = r.text
    # SSE: data: lauks var stiepties pāri vairākām fiziskām rindiņām.
    # Apvieno visas rindiņas, kas pieder vienam data: laukam (līdz nākamajai event:/tukšai).
    raw_lines = text.splitlines()
    data_parts = []
    in_data = False
    for l in raw_lines:
        if l.startswith("data: "):
            in_data = True
            data_parts.append(l[6:])
        elif in_data and l and not l.startswith("event:"):
            # turpinājums (SSE sadala garu JSON pa rindiņām)
            data_parts.append(l)
        elif in_data and (l.startswith("event:") or not l):
            in_data = False
    if not data_parts:
        return json.loads(text)
    joined = "".join(data_parts)
    try:
        obj = json.loads(joined)
        if "result" in obj or "error" in obj:
            return obj
    except Exception:
        pass
    open("/tmp/mcp_raw_debug.txt", "w").write(text)
    raise RuntimeError(f"Neizdevās parsēt MCP atbildi (len={len(text)})")


def extract_inner(res):
    """Izvelk ligzdoto composio atbildi no MCP content."""
    try:
        return json.loads(res["result"]["content"][0]["text"])
    except Exception:
        return res


def stage_image(key, image_path, http_port=8123):
    """Servē bildi + staged uz composio S3. Atgriež s3key."""
    # 1. servē bildi
    img_name = os.path.basename(image_path)
    serve_dir = os.path.dirname(image_path)
    subprocess.run(
        ["pkill", "-f", f"http.server {http_port}"], capture_output=True
    )
    subprocess.Popen(
        ["setsid", "python3", "-m", "http.server", str(http_port), "--bind", "0.0.0.0"],
        cwd=serve_dir,
        stdout=open("/tmp/http_serve.log", "a"),
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )
    time.sleep(1.5)
    # 2. workbench: lejupielādē + upload_local_file
    code = f"""
import urllib.request, os
url = 'http://169.58.103.143:{http_port}/{img_name}'
urllib.request.urlretrieve(url, '/home/user/xpost.png')
print('downloaded', os.path.getsize('/home/user/xpost.png'))
res, err = upload_local_file('/home/user/xpost.png')
print('err:', err)
print('s3key:', res.get('s3key') if res else None)
"""
    res = rpc("tools/call", {
        "name": "COMPOSIO_REMOTE_WORKBENCH",
        "arguments": {"code_to_execute": code, "current_step": "STAGING_FILE_TO_S3", "session_id": SESSION_ID},
    }, key)
    inner = extract_inner(res)
    stdout = inner.get("data", {}).get("stdout", "")
    # izvelc s3key no stdout
    for line in stdout.splitlines():
        if line.startswith("s3key:"):
            return line.split("s3key:", 1)[1].strip()
    raise RuntimeError(f"Nav s3key stdout: {stdout[:500]}")


def multi_execute(key, tool_slug, args):
    """Izsaukt app rīku caur COMPOSIO_MULTI_EXECUTE_TOOL (app rīki nav tiešie MCP rīki)."""
    res = rpc("tools/call", {
        "name": "COMPOSIO_MULTI_EXECUTE_TOOL",
        "arguments": {
            "tools": [{"tool_slug": tool_slug, "arguments": args}],
            "sync_response_to_workbench": False,
            "current_step": "EXECUTING_TOOL",
            "session_id": SESSION_ID,
        },
    }, key)
    inner = extract_inner(res)
    data = inner.get("data", {})
    results = data.get("results", [])
    if results and results[0].get("response", {}).get("successful"):
        return results[0]["response"]["data"]
    raise RuntimeError(f"{tool_slug} neizdevās: {json.dumps(inner)[:600]}")


def upload_media(key, s3key):
    data = multi_execute(key, "TWITTER_UPLOAD_MEDIA", {
        "media": {"name": "xpost.png", "mimetype": "image/png", "s3key": s3key},
        "media_category": "tweet_image",
        "media_type": "image/png",
    })
    # media_id var būt data.id vai data.data.id
    d = data.get("data", data)
    return d.get("id") or d.get("media_id")


def create_post(key, text, media_id):
    data = multi_execute(key, "TWITTER_CREATION_OF_A_POST", {
        "text": text,
        "media_media_ids": [media_id],
    })
    d = data.get("data", data)
    return d.get("id")


def main():
    text = sys.argv[1]
    image_path = sys.argv[2] if len(sys.argv) > 2 else None
    key = get_key()
    print("1. Stage image...")
    s3key = stage_image(key, image_path)
    print("   s3key:", s3key)
    print("2. Upload media...")
    media_id = upload_media(key, s3key)
    print("   media_id:", media_id)
    print("3. Create post...")
    tweet_id = create_post(key, text, media_id)
    print("   tweet_id:", tweet_id)
    print("GATAVS — post publicēts:", tweet_id)


if __name__ == "__main__":
    main()
