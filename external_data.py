"""
Real keyword data with a simple API key (no OAuth) — plus free Google Trends.
These are the alternatives to the Google Ads API for actual volume/competition numbers.
"""
import requests


# ---------- Keywords Everywhere ----------
def get_keywords_everywhere(api_key: str, keywords: list, country="us", currency="USD"):
    """https://api.keywordseverywhere.com — pay-as-you-go credits, real GKP-sourced volume."""
    url = "https://api.keywordseverywhere.com/v1/get_keyword_data"
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {
        "country": country,
        "currency": currency,
        "dataSource": "gkp",
        "kw[]": keywords,
    }
    resp = requests.post(url, headers=headers, data=data, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    rows = []
    for item in payload.get("data", []):
        rows.append({
            "keyword": item.get("keyword"),
            "avg_monthly_searches": item.get("vol"),
            "cpc": (item.get("cpc") or {}).get("value"),
            "competition": item.get("competition"),
            "trend": item.get("trend"),
        })
    return rows, payload.get("credits")


# ---------- Semrush ----------
def get_semrush_data(api_key: str, keywords: list, database="us"):
    """
    https://www.semrush.com/api-analytics/ — 'Batch Keyword Overview' (phrase_these),
    up to 100 phrases per call, newline-separated.
    """
    url = "https://api.semrush.com/"
    rows = []
    for i in range(0, len(keywords), 100):
        batch = keywords[i:i + 100]
        params = {
            "type": "phrase_these",
            "key": api_key,
            "phrase": "\n".join(batch),
            "database": database,
            "export_columns": "Ph,Nq,Cp,Co,Kd",
        }
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        text = resp.text.strip()
        if not text or text.startswith("ERROR"):
            raise ValueError(text or "Semrush returned no data — check your key/plan quota.")
        lines = text.splitlines()
        for line in lines[1:]:  # skip header row
            parts = line.split(";")
            if len(parts) >= 5:
                rows.append({
                    "keyword": parts[0],
                    "avg_monthly_searches": _to_num(parts[1]),
                    "cpc": _to_num(parts[2]),
                    "competition": _to_num(parts[3]),
                    "keyword_difficulty": _to_num(parts[4]),
                })
    return rows


def _to_num(s):
    try:
        return float(s) if "." in s else int(s)
    except (ValueError, TypeError):
        return s


# ---------- Google Trends (free, no key) ----------
def get_google_trends(keywords: list, timeframe="today 12-m", geo=""):
    """
    Free but unofficial (scrapes the public Trends UI via pytrends) — relative interest
    0-100 per keyword, not an absolute monthly search count. Max 5 keywords per call.
    """
    from pytrends.request import TrendReq
    pytrends = TrendReq(hl="en-US", tz=360)
    rows = []
    for i in range(0, len(keywords), 5):
        batch = keywords[i:i + 5]
        pytrends.build_payload(batch, timeframe=timeframe, geo=geo)
        df = pytrends.interest_over_time()
        for kw in batch:
            avg_interest = round(df[kw].mean(), 1) if kw in df.columns and not df.empty else None
            rows.append({"keyword": kw, "avg_relative_interest": avg_interest})
    return rows
