import uuid

posts = {}
shortners = []
premium = set()

# POSTS
async def save_post(file_ids):
    pid = str(uuid.uuid4())
    posts[pid] = file_ids
    return pid

async def get_post(pid):
    return posts.get(pid)

# SHORTNER
async def add_shortner(url, api):
    shortners.append({"url": url, "api": api})

async def get_shortner():
    return shortners[0] if shortners else None

async def remove_shortner():
    if shortners:
        shortners.pop(0)

# PREMIUM
async def add_premium(uid):
    premium.add(uid)

async def remove_premium(uid):
    premium.discard(uid)

async def is_premium(uid):
    return uid in premium
