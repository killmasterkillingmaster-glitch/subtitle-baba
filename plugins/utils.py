import json
import os
import random
import requests

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        if filename == "channels.json": return []
        return [] if any(x in filename for x in ["shorteners", "premium"]) else {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filename, data):
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_short_link(long_url: str) -> str:
    shorteners = load_json("shorteners.json")
    if not shorteners:
        return long_url # Agar shortener add nahi hai toh direct link dega
    
    short = random.choice(shorteners)
    try:
        r = requests.get(
            f"{short['url']}api",
            params={"api": short['api'], "url": long_url},
            timeout=10
        )
        data = r.json()
        if data.get("status") == "success":
            return data["shortenedUrl"]
    except Exception as e:
        print(f"Shortener API Error: {e}")
    return long_url
