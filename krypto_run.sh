#!/bin/bash
# Kripto nedēļas pārskats — pirmdienās 09:00 LV (VPS 08:00 Berlin).
# Sūta Telegram: infografika + teksts + footer kriptonr1.xyz, tad X postu.
export SEND_TELEGRAM=1
export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"
/root/.hermes/venv/bin/python3 /root/scripts/krypto_weekly.py >> /tmp/krypto_weekly.log 2>&1
