import requests, os
from datetime import datetime, UTC, timezone    
import json
import csv
import pandas as pd
import calendar
from drive_sync import upload_file_preserving_tree
from zoneinfo import ZoneInfo


# =====================
# CONFIGURATION
# =====================
API_USER = os.getenv("DATAFORSEO_USER", "seo@neatplay.com")
API_PASS = os.getenv("DATAFORSEO_PASS", "7cbf8facb2e8b41e")
AUTH = (API_USER, API_PASS)     
SCREENSHOTS_ROOT_ID = os.getenv("SCREENSHOTS_ROOT_ID", "103gC0AL0chUzZjLY0YPo84ARGX-PuUhc")

BASE_DIR = r"C:\Users\Christian\Desktop\Leap Square\Leap Square\Scripts\SERP ScreenShots"
SCREEN_DIR = os.path.join(BASE_DIR, "Screenshots")
JSON_DIR   = os.path.join(BASE_DIR, "Json")
REPORT_DIR = os.path.join(BASE_DIR, "Reports")
REPORTS_ROOT_ID = os.getenv("REPORTS_ROOT_ID", "1IuUNGrI3yyVw67t5D9T418mDlG_A-6ch")

os.makedirs(SCREEN_DIR, exist_ok=True)
os.makedirs(JSON_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

KEYWORDS = ["bets 10", "bets 10 giris", "bets 10 giriş", "10 bets", "bets 10 güncel", "b10", "bet 10", "bet10", "10 bets", "10 bet", "best10", "bets10", "10bet", "10bets", "bets 10 giriş güncel", "bets10 giriş güncel"
            ]
ENGINES  = [("google", "organic")]
DEVICES  = ["mobile"]

# Location: Turkiye
USE_LOCATION_CODE = False
LOCATION_NAME = "Turkiye"     
LOCATION_CODE = 2840      
LANGUAGE_CODE = "tr"

TOP_N_ORGANIC = 10
TOP_N_PAID = 5
UTC = timezone.utc
MALTA_TZ = ZoneInfo("Europe/Malta")

def is_in_allowed_window(dt_local):
    """
    Allowed windows (Europe/Malta local time):
    - Mon–Thu:    17:00 → next day 08:00
    - Fri:        17:00 → Monday 08:00 (full weekend)
    So: Sat & Sun: allowed 24h; otherwise, allowed if time >=17:00 or <08:00
    """
    wd = dt_local.weekday()  # Monday=0 ... Sunday=6
    h = dt_local.hour
    # Weekend: allowed all day
    if wd in (5, 6):  # Sat(5), Sun(6)
        return True
    # Weekdays:
    if h >= 16 or h < 8:
        return True
    return False

def ensure_window_or_exit():
    now_local = datetime.now(MALTA_TZ)
    if not is_in_allowed_window(now_local):
        print(f"[Scheduler] Outside active window for Europe/Malta. Now: {now_local.isoformat()}")
        raise SystemExit(0)  # exit gracefully; Render considers this a successful run

def upload_if_exists(local_path, label="archivo"):
    try:
        if not os.path.isfile(local_path):
            print(f"[Drive] {label} doesn't exist, not to be uploaded:", local_path)
            return None, None
        fid, link = upload_file_preserving_tree(local_path)
        print(f"[Drive] ✅ Uploaded {label}: {link}")
        return fid, link
    except Exception as e:
        print(f"[Drive] ❌ Error while uploading {label}: {e}")
        return None, None

def get_screenshot_dir(base_dir):
    """Returns the Folders: BASE/AAAA/MM-NameMonth/DDNameMonth (e.i. 2025/10-October/16October) and it creates it if it doesn't exist."""
    now = now_utc()
    year = now.strftime("%Y")                               # '2025'
    month_num = now.strftime("%m")                          # '10'
    month_name = calendar.month_name[int(month_num)]        # 'October'
    day_name = now.strftime("%d") + month_name              # '16October'
    month_folder = f"{month_num}-{month_name}"              # '10-October'

    path = os.path.join(base_dir, year, month_folder, day_name)
    os.makedirs(path, exist_ok=True)
    return path

def now_utc():
    return datetime.now(UTC)

def ts_stamp():
    return now_utc().strftime("%Y%m%d_%H%M%S")

def today_str():
    return now_utc().strftime("%Y%m%d")

def post_json(url, payload, timeout=180):
    # DataForSEO v3
    r = requests.post(url, json=payload, auth=AUTH, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if not data or "tasks" not in data or not data["tasks"]:
        raise RuntimeError(f"🚨 API without tasks: {r.text}")
    t = data["tasks"][0]
    if t.get("status_code") != 20000:
        raise RuntimeError(f"❌ Task error {t.get('status_code')}: {t.get('status_message')} | {r.text}")
    return data

def fetch_serp(engine, se_type, keyword, device):
    url = f"https://api.dataforseo.com/v3/serp/{engine}/{se_type}/live/advanced"
    task = {
        "keyword": keyword,
        "language_code": LANGUAGE_CODE,
        "device": device
    }
    if USE_LOCATION_CODE:
        task["location_code"] = LOCATION_CODE
    else:
        task["location_name"] = LOCATION_NAME
    payload = [task]
    js = post_json(url, payload)
    return js["tasks"][0] 

def fetch_screenshot(task_id):
    sjs = post_json("https://api.dataforseo.com/v3/serp/screenshot", [{"task_id": task_id}])
    return sjs["tasks"][0]["result"][0]["items"][0]["image"]

def save_image(url, engine, keyword, device):
    ts = ts_stamp()
    name = f"{engine}_{device}_{keyword}_{ts_stamp()}.png".replace(" ", "_")
    day_dir = get_screenshot_dir(SCREEN_DIR)
    path = os.path.join(day_dir, name)
    img = requests.get(url, timeout=180).content
    with open(path, "wb") as f:
        f.write(img)
        print(f"✅ Saved Locally: {path}")
    return path

def ensure_raw_header(csv_path):
    header = [
        "ts_utc", "engine", "se_type", "device", "keyword",
        "location_selector", "location_value", "language_code",
        "result_type", "is_paid", "rank_group", "rank_absolute", "block_position",
        "title", "url", "domain", "description", "ad_aclk",
        "task_id", "screenshot_path", "screenshot_url",
    ]
    needs = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
    if needs:
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(header)

def append_rows(csv_path, rows):
    if not rows: return
    with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        for r in rows:
            w.writerow([
                r["ts_utc"], r["engine"], r["se_type"], r["device"], r["keyword"],
                r["location_selector"], r["location_value"], r["language_code"],
                r["result_type"], r["is_paid"], r["rank_group"], r["rank_absolute"], r["block_position"],
                r["title"], r["url"], r["domain"], r["description"], r["ad_aclk"],
                r["task_id"], r["screenshot_path"], r["screenshot_url"]
            ])

def extract_top_rows(task_block, engine, se_type, keyword, device, png_path, png_url):
    rows = []
    res = task_block.get("result") or []
    if not res: return rows
    items = res[0].get("items", []) or []
    organic_count = 0
    paid_count = 0
    for it in items:
        t = it.get("type")  # 'organic', 'paid',

        # Type of SERP
        if t == "organic":
            organic_count += 1
            if organic_count > TOP_N_ORGANIC:
                continue
        elif t == "paid":
            paid_count += 1
            if paid_count > TOP_N_PAID:
                continue
        else:
            # Ignore other types like 'shopping'
            continue
        rows.append({
            "ts_utc": now_utc().strftime("%Y-%m-%d %H:%M:%S"),
            "engine": engine,
            "se_type": se_type,
            "device": device,
            "keyword": keyword,
            "location_selector": ("code" if USE_LOCATION_CODE else "name"),
            "location_value": (LOCATION_CODE if USE_LOCATION_CODE else LOCATION_NAME),
            "language_code": LANGUAGE_CODE,

            "result_type": t,                      # 'organic' | 'paid' | 'shopping'
            "is_paid": True if t == "paid" else False,

            #Metadata from the result
            "rank_group": it.get("rank_group"),
            "rank_absolute": it.get("rank_absolute"),
            "block_position": it.get("block_position"),
            "title": it.get("title"),
            "url": it.get("url"),
            "domain": it.get("domain"),
            "description": it.get("description"),
            "ad_aclk": it.get("ad_aclk"),

            # Traceability
            "task_id": task_block.get("id"),
            "screenshot_path": png_path,
            "screenshot_url": png_url
        })
    return rows

def main():
    ensure_window_or_exit()
    day = today_str()
    raw_csv = os.path.join(REPORT_DIR, f"serp_raw_{ts_stamp()}.csv")
    ensure_raw_header(raw_csv)

    day_json_dir = os.path.join(JSON_DIR, day)
    os.makedirs(day_json_dir, exist_ok=True)

    for engine, se_type in ENGINES:
        for device in DEVICES:
            for kw in KEYWORDS:
                try:
                    print(f"[{ts_stamp()}] {engine.upper()} | {device} | {kw}")
                    task = fetch_serp(engine, se_type, kw, device)
                    task_id = task["id"]

                    json_path = os.path.join(day_json_dir, f"{engine}_{device}_{kw}_{ts_stamp()}.json".replace(" ","_"))
                    with open(json_path, "w", encoding="utf-8") as jf:
                        json.dump({"tasks":[task]}, jf, ensure_ascii=False, indent=2)

                    image_url = fetch_screenshot(task_id)
                    png_path = save_image(image_url, engine, kw, device)
                    print("✅ Saved on Drive:", png_path)
                    try:
                        _, drive_png_link = upload_file_preserving_tree(png_path, root_id=SCREENSHOTS_ROOT_ID)
                        print("[Drive]✅ PNG Uploaded:", drive_png_link)
                    except Exception as e:
                        print("[Drive] ❌ Error while uploading PNG:", e)

                    rows = extract_top_rows(task, engine, se_type, kw, device, png_path, image_url)
                    append_rows(raw_csv, rows)

                except Exception as e:
                    print(f"❌ Error {engine}/{device}/{kw}: {e}")
                    
    try:
        _, report_link = upload_file_preserving_tree(raw_csv, root_id=REPORTS_ROOT_ID)
        print("[Drive] ✅ Report uploaded:", report_link)
    except Exception as e:
        print("[Drive] ❌ Error while uploading report:", e)
    print(f"\n✅ CSV Ready: {raw_csv}")

if __name__ == "__main__":
    main()

