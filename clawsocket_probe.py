# -*- coding: utf-8 -*-
import os
from clawsocket_compat import ClawSocketClient
requested=os.environ.get("GPT_MODEL") or "gpt-6-astra"
client=ClawSocketClient(timeout=30,retries=1)
info=client.preflight(requested)
print("--- ClawSocket diagnostic ---")
print("Base URL:",client.base_url)
print("Requested model:",requested)
print("Exact available:",info.get("exact_available"))
print("Matched:",info.get("matched"))
print("Available model count:",info.get("available_count"))
print("Available preview:",", ".join(info.get("available_preview") or []))
print("Auto fallback:",os.environ.get("CLAWSOCKET_AUTO_FALLBACK","1"))
print("GPT fallback:",os.environ.get("GPT_FALLBACK_MODEL") or "<not set>")
