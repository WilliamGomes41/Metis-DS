#!/usr/bin/env python3
"""Minimal client example for V&VN Data Services Product API v1."""
import json
import os
import urllib.request

base = os.getenv("VVN_API_BASE", "http://127.0.0.1:8080")
key = os.environ["VVN_API_KEY"]
query = os.getenv("VVN_QUERY", "Wanneer gebruik je de risicofactorenscore?")
body = json.dumps({"query": query, "top_k": 5}).encode("utf-8")
req = urllib.request.Request(
    base + "/v1/retrieve",
    data=body,
    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req) as response:
    print(json.dumps(json.load(response), ensure_ascii=False, indent=2))
