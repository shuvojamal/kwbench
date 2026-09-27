"""
Keyword Bench — local dashboard for bulk keyword work.
Run:  python app.py   then open http://127.0.0.1:5050
Credentials are saved to config.json IN THIS FOLDER ONLY — never sent anywhere
except the AI/API provider you pick for a given action.
"""
import io
import json
import os
import threading
import webbrowser

import pandas as pd
from flask import Flask, jsonify, request, send_file, send_from_directory

import external_data
import providers
import sitemap_tools

app = Flask(__name__, static_folder="static")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

CHUNK_SIZE = 300           # keywords per AI call when cleaning bulk lists
GENERATE_ANGLES = [
    "broad informational queries (how/what/why/guide/tips)",
    "commercial comparison queries (best/top/vs/review)",
    "transactional buying queries (price/cost/buy/near me/hire)",
    "long-tail specific variants (size, material, style, room type, budget)",
    "question-based queries (can/should/does/is it worth)",
    "local and location-based variants",
    "seasonal, trend, or year-specific variants",
    "problem/troubleshooting queries (fix, not working, vs alternative)",
]


# ---------- config ----------
def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
            cfg.setdefault("keywords_everywhere", "")
            cfg.setdefault("semrush", "")
            return cfg
    return {"openai": "", "gemini": "", "claude": "", "keywords_everywhere": "", "semrush": "", "google_ads": {}}


def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


@app.route("/api/keys", methods=["GET"])
def get_keys():
    cfg = load_config()
    return jsonify({
        "openai": bool(cfg.get("openai")),
        "gemini": bool(cfg.get("gemini")),
        "claude": bool(cfg.get("claude")),
        "keywords_everywhere": bool(cfg.get("keywords_everywhere")),
        "semrush": bool(cfg.get("semrush")),
        "google_ads": bool(cfg.get("google_ads", {}).get("developer_token")),
    })


@app.route("/api/keys", methods=["POST"])
def set_keys():
    cfg = load_config()
    body = request.json or {}
    for k in ("openai", "gemini", "claude", "keywords_everywhere", "semrush"):
        if body.get(k):
            cfg[k] = body[k]
    if body.get("google_ads"):
        cfg["google_ads"] = {**cfg.get("google_ads", {}), **body["google_ads"]}
    save_config(cfg)
    return jsonify({"ok": True})


def get_key(provider):
    cfg = load_config()
    key = cfg.get(provider)
    if not key:
        raise ValueError(f"No API key saved for {provider}. Add it in Settings.")
    return key


# ---------- clean & merge ----------
@app.route("/api/clean", methods=["POST"])
def clean_keywords():
    provider = request.form.get("provider", "claude")
    f = request.files["file"]
    ext = f.filename.rsplit(".", 1)[-1].lower()
    if ext == "csv":
        df = pd.read_csv(f)
    else:
        df = pd.read_excel(f)

    kw_col = next((c for c in df.columns if "keyword" in c.lower()), df.columns[0])
    keywords = sorted(set(str(k).strip() for k in df[kw_col].dropna() if str(k).strip()))

    api_key = get_key(provider)
    chunks = [keywords[i:i + CHUNK_SIZE] for i in range(0, len(keywords), CHUNK_SIZE)]
    all_rows = []
    for chunk in chunks:
        prompt = (
            "Here is a list of SEO keywords. Group keywords that share the same search intent "
            "(near-duplicates, plurals, word-order variants, same underlying question) and keep only ONE "
            "best keyword per group — the clearest, most natural, highest-value phrasing. Drop junk/nonsense "
            "keywords entirely.\n\n"
            'Reply with ONLY a JSON array, one object per kept keyword: {"keyword": string, "intent": one of '
            '"informational"|"commercial"|"transactional"|"navigational"|"local", "merged_from": array of the '
            "other raw keywords folded into this one (empty array if none)}.\n\nKeywords:\n" + "\n".join(chunk)
        )
        text = providers.call_ai(provider, api_key, prompt)
        rows = providers.extract_json(text)
        if isinstance(rows, list):
            all_rows.extend(rows)

    return jsonify({"total_input": len(keywords), "rows": all_rows})


# ---------- generate from seed ----------
@app.route("/api/generate", methods=["POST"])
def generate_keywords():
    body = request.json or {}
    seed = body.get("seed", "").strip()
    provider = body.get("provider", "claude")
    target = int(body.get("target", 500))
    if not seed:
        return jsonify({"error": "Seed keyword required"}), 400

    api_key = get_key(provider)
    seen = {}
    angle_i = 0
    attempts = 0
    while len(seen) < target and attempts < len(GENERATE_ANGLES) * 3:
        angle = GENERATE_ANGLES[angle_i % len(GENERATE_ANGLES)]
        angle_i += 1
        attempts += 1
        prompt = (
            f'Generate 60-80 distinct, realistic SEO keywords for the seed topic "{seed}", '
            f"focused specifically on: {angle}. Real phrases a searcher would type — no filler, no near-duplicates "
            "of each other.\n\n"
            'Reply with ONLY a JSON array of {"keyword": string, "intent": one of '
            '"informational"|"commercial"|"transactional"|"navigational"|"local"}.'
        )
        try:
            text = providers.call_ai(provider, api_key, prompt)
            rows = providers.extract_json(text)
        except Exception:
            continue
        if isinstance(rows, list):
            for r in rows:
                kw = str(r.get("keyword", "")).strip().lower()
                if kw and kw not in seen:
                    seen[kw] = r

    return jsonify({"rows": list(seen.values())[:target]})


# ---------- competitor sitemap -> keywords ----------
@app.route("/api/sitemap", methods=["POST"])
def sitemap_keywords():
    body = request.json or {}
    domain = body.get("domain", "").strip()
    provider = body.get("provider", "claude")
    target = int(body.get("target", 300))
    if not domain:
        return jsonify({"error": "Competitor domain required"}), 400

    urls = sitemap_tools.fetch_urls(domain, max_urls=800)
    phrases = sitemap_tools.slugs_to_phrases(urls)
    titles = sitemap_tools.sample_titles(urls, limit=40)

    api_key = get_key(provider)
    material = "URL slugs:\n" + "\n".join(phrases[:500]) + "\n\nPage titles sample:\n" + "\n".join(titles)
    prompt = (
        f"Below is raw material scraped from a competitor site's sitemap ({domain}): URL slugs turned into "
        "phrases, and a sample of page titles. Infer the topics this site targets and produce a clean bulk "
        f"keyword list of up to {target} SEO keywords for writing similar/competing articles. Deduplicate near-"
        "identical entries and drop anything that isn't a real search phrase (e.g. leftover CMS/tag/category "
        "junk).\n\n"
        'Reply with ONLY a JSON array of {"keyword": string, "intent": one of '
        f'"informational"|"commercial"|"transactional"|"navigational"|"local"}}.\n\n{material}'
    )
    text = providers.call_ai(provider, api_key, prompt)
    rows = providers.extract_json(text)
    return jsonify({"url_count": len(urls), "rows": rows if isinstance(rows, list) else []})


# ---------- Keywords Everywhere (real data, simple API key) ----------
@app.route("/api/keywords-everywhere", methods=["POST"])
def keywords_everywhere_route():
    body = request.json or {}
    seeds = [s.strip() for s in body.get("seeds", "").split(",") if s.strip()]
    if not seeds:
        return jsonify({"error": "Enter at least one keyword"}), 400
    try:
        api_key = get_key("keywords_everywhere")
        rows, credits = external_data.get_keywords_everywhere(api_key, seeds)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"rows": rows, "credits_remaining": credits})


# ---------- Semrush (real data, simple API key) ----------
@app.route("/api/semrush", methods=["POST"])
def semrush_route():
    body = request.json or {}
    seeds = [s.strip() for s in body.get("seeds", "").split(",") if s.strip()]
    database = body.get("database", "us")
    if not seeds:
        return jsonify({"error": "Enter at least one keyword"}), 400
    try:
        api_key = get_key("semrush")
        rows = external_data.get_semrush_data(api_key, seeds, database=database)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"rows": rows})


# ---------- Google Trends (free, no key) ----------
@app.route("/api/google-trends", methods=["POST"])
def google_trends_route():
    body = request.json or {}
    seeds = [s.strip() for s in body.get("seeds", "").split(",") if s.strip()]
    if not seeds:
        return jsonify({"error": "Enter at least one keyword"}), 400
    try:
        rows = external_data.get_google_trends(seeds)
    except Exception as e:
        return jsonify({"error": f"Trends request failed (Google rate-limits this often — wait a bit and retry): {e}"}), 500
    return jsonify({"rows": rows})


# ---------- Google Ads real data ----------
@app.route("/api/google-ads", methods=["POST"])
def google_ads_ideas():
    import google_ads_tools
    body = request.json or {}
    seeds = [s.strip() for s in body.get("seeds", "").split(",") if s.strip()]
    geo = body.get("geo_target_id", "2840")
    cfg = load_config()
    ga = cfg.get("google_ads", {})
    required = ["developer_token", "client_id", "client_secret", "refresh_token", "customer_id"]
    missing = [k for k in required if not ga.get(k)]
    if missing:
        return jsonify({"error": f"Missing Google Ads settings: {', '.join(missing)}"}), 400
    try:
        rows = google_ads_tools.get_keyword_ideas(ga, seeds, geo_target_id=geo)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"rows": rows})


# ---------- download helper ----------
@app.route("/api/download", methods=["POST"])
def download_xlsx():
    body = request.json or {}
    rows = body.get("rows", [])
    filename = body.get("filename", "keywords.xlsx")
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=filename,
                      mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


if __name__ == "__main__":
    threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5050")).start()
    app.run(port=5050, debug=False)
