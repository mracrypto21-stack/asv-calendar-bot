#!/usr/bin/env python3
"""kie.ai premium fona ģenerēšana ASV ekonomikas dashboardam.

Ģenerē tikai FONU (bez teksta/cipariem) caur kie.ai Seedream 5.0 Lite —
dziļš gandrīz melns gradients, neona svečturi, hologrāfisks vērsis (pa kreisi)
un lācis (pa labi). Katru dienu fons atšķiras (seed = dienu skaits kopš epochas
→ garantēti mainīgs starp nedēļām, atšķirībā no agrākā ISO nedēļas +1, kas
kļūdaini deva gandrīz identiskas bildes).

Datus (skaitļus/tekstu) uzliek HTML→PNG renderētājs (asv_dashboard_html.py),
jo AI modeļi slikti renderē ciparus. Šis modulis tikai sagatavo fonu.

Lietošana:
    python3 kie_bg.py <out.png> [seed]
"""
import os
import time
import json
import random
import urllib.request
from datetime import datetime

import requests

KIE_API = "https://api.kie.ai"
KIE_MODEL = "seedream/5-lite-text-to-image"   # lēts (5.5 kredīti), labs
ASPECT = "4:3"
QUALITY = "basic"


def load_api_key():
    key = os.environ.get("KIE_AI_API_KEY")
    if key:
        return key.strip()
    here = os.path.dirname(os.path.abspath(__file__))
    for env_path in (os.path.join(here, ".env"), "/root/.hermes/.env"):
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("KIE_AI_API_KEY="):
                        return line.strip().split("=", 1)[1].strip().strip("'").strip('"')
    raise RuntimeError("KIE_AI_API_KEY nav atrasts (env vai .env)")


def build_prompt(seed, theme_idx):
    """Uz seed + theme_idx balstīts fona prompt.

    theme_idx rotē cauri BŪTISKI atšķirīgām tēmām (katru nedēļu cita), lai
    fons garantēti mainītos — atšķirībā no agrākā seed-only pieejas, kur
    KIE.AI ar gandrīz vienādu promptu (sveces + bullish bulta) ģenerēja
    gandrīz vienādu fonu (lietotāja sūdzība 2026-09-21).
    """
    rng = random.Random(seed)

    lighting = [
        "soft ambient glow", "dramatic rim lighting", "subtle volumetric light",
        "gentle neon glow", "moody cinematic lighting",
    ]
    style = [
        "premium fintech aesthetic", "minimal futuristic", "sleek modern",
        "cyberpunk elegance", "high-end trading terminal",
    ]
    accent = ["gold", "amber", "warm gold", "golden", "rose gold", "bronze"]
    light = rng.choice(lighting)
    st = rng.choice(style)
    acc = rng.choice(accent)

    # --- BŪTISKI atšķirīgas fona tēmas (bez obligātajām svecēm katrā) ---
    # Katrai tēmai sapludināta vairākkrāsu palete, kas rotē pa nedēļām
    # (theme_idx) — daudzveidīgs, interessants un bez apnikušā zilā kā
    # dominējošā (lietotājs 2026-09-21).
    themes = [
        # 0 — vērsis/lācis, zelta/sarkanā + dzintara
        lambda: (
            "a single stylized holographic wireframe bull charging upward, body "
            "glowing warm gold blending into amber, on the left, and a matching "
            "holographic wireframe bear prowling, deep crimson blending into "
            "burgundy, on the right, sparse dark background"
        ),
        # 1 — pilsētas siluets, dzintara/oranžā + rozā/rožu zelta
        lambda: (
            "a sleek futuristic financial district skyline silhouette at night, "
            "glowing amber, orange and rose-gold windows, warm neon gradients "
            "along the towers, faint chart lines drawn through a warm dusk sky"
        ),
        # 2 — abstraktas 3D joslas, hroma + rozā/violets/ciāna
        lambda: (
            "abstract glossy 3D bar chart columns rising from the bottom, polished "
            "chrome and glass with a rich gradient glow blending magenta, violet "
            "and a hint of teal, minimal and premium, deep charcoal background"
        ),
        # 3 — globālā karte, zaļa/emerald + zelta tīkla gaisma
        lambda: (
            "a dark world map with glowing emerald, teal and golden connection "
            "arcs between financial hubs, particles of green and gold light, "
            "global trading network at night"
        ),
        # 4 — dziļš kosmoss, violets/rozā + zelta (bez zilā)
        lambda: (
            "deep space nebula in rich violet and magenta blending into rose-gold, "
            "faint glowing planet rings, scattered stars, subtle comet streaks of "
            "gold and pink, premium finance meets cosmos"
        ),
        # 5 — minimāla līnija, dzeltens + zaļš + platīns
        lambda: (
            "a minimal clean upward-trending neon line with soft arrowhead in "
            "pale yellow blending into mint green, subtle geometric circles and "
            "polygons floating in warm charcoal, elegant fintech minimalism"
        ),
    ]
    scene = themes[theme_idx % len(themes)]()

    prompt = (
        "Premium financial trading dashboard background, deep near-black premium "
        "gradient (pure black center fading to very dark charcoal edges), "
        f"{scene}, {light}, {st}, subtle {acc} glow, "
        "no text, no numbers, no letters, no words, no labels, "
        "empty background for data overlay"
    )
    return prompt


def check_credits(api_key=None):
    """Atgriež atlikušo kredītu skaitu (float). Ja neizdodas, raise."""
    if api_key is None:
        api_key = load_api_key()
    resp = requests.get(
        f"{KIE_API}/api/v1/chat/credit",
        headers={"Authorization": f"Bearer {api_key}"}, timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 200:
        raise RuntimeError(f"kie.ai credit kļūda: {data}")
    return float(data.get("data", 0))


def create_task(prompt, api_key):
    payload = {
        "model": KIE_MODEL,
        "input": {
            "prompt": prompt,
            "aspect_ratio": ASPECT,
            "quality": QUALITY,
            "output_format": "png",
            "nsfw_checker": False,
        },
    }
    resp = requests.post(
        f"{KIE_API}/api/v1/jobs/createTask",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload, timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 200:
        raise RuntimeError(f"kie.ai createTask kļūda: {data}")
    return data["data"]["taskId"]


def poll_task(task_id, api_key, timeout=180):
    url = f"{KIE_API}/api/v1/jobs/recordInfo?taskId={task_id}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        state = data.get("state")
        if state == "success":
            urls = data.get("resultJson", "")
            try:
                urls = json.loads(urls).get("resultUrls", [])
            except Exception:
                urls = []
            if urls:
                return urls[0]
            raise RuntimeError("kie.ai: success, bet nav rezultāta URL")
        if state in ("failed", "error"):
            raise RuntimeError(f"kie.ai uzdevums neizdevās: {data.get('failMsg')}")
        time.sleep(5)
    raise RuntimeError("kie.ai: uzdevuma apstrādes taimauts")


def download(url, out_path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        with open(out_path, "wb") as f:
            f.write(r.read())
    return out_path


def generate_background(out_path, seed=None):
    """Ģenerē premium fonu caur kie.ai un saglabā to out_path."""
    if seed is None:
        # dienu skaits kopš epochas → katru dienu MAINĪGS seed, lai pat vienas
        # tēmas ietvaros fons nedaudz atšķirtos.
        seed = int(time.time() / 86400)  # piem. 20700 → pavisam cits fons weekly
    # theme_idx rotē cauri BŪTISKI atšķirīgām tēmām pa ISO nedēļām — katru
    # nedēļu garantēti cita fona tēma (ne tikai seed +1, kas KIE.AI deva
    # gandrīz identiskas bildes — lietotāja sūdzība 2026-09-21).
    iso = datetime.now().isocalendar()
    theme_idx = iso[1]  # ISO nedēļas numurs (garantē +1 katru nedēļu)
    api_key = load_api_key()
    prompt = build_prompt(seed, theme_idx)
    print(f"🎨 kie.ai fons (seed={seed}, theme#{theme_idx})")
    task_id = create_task(prompt, api_key)
    url = poll_task(task_id, api_key)
    download(url, out_path)
    print(f"✅ Fons saglabāts: {out_path}")
    return out_path


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/kie_bg.png"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else None
    generate_background(out, seed)
