import json
import os
import random
import requests
from datetime import datetime, timedelta

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return [] if any(x in filename for x in ["shorteners","premium","forcesub"]) else {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filename, data):
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# GPLinks exact API (jo tune dashboard se diya hai)
def get_short_link(long_url: str) -> str:
    shorteners = load_json("shorteners.json")
    if not shorteners:
        return long_url
    short = random.choice(shorteners)
    try:
        r = requests.get(
            "https://api.gplinks.com/api",
            params={"api": short["api_key"], "url": long_url},
            timeout=10
        )
        data = r.json()
        if data.get("status") == "success":
            return data["shortenedUrl"]
    except:
        pass
    return long_url
