# Keyword Bench

A local dashboard for bulk keyword work: clean/merge SEMrush exports, generate
500+ keywords from a seed, mine a competitor's sitemap for article ideas, and
(optionally) pull real Google Ads Keyword Planner data. Works with GPT, Gemini,
or Claude — pick per action.

## Setup

```bash
cd keyword_bench
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

If you don't plan to use the real Google Ads tab, remove the `google-ads` line
from `requirements.txt` first — it's a heavier install and not needed for the
AI-only tools.

## Run

```bash
python app.py
```

Opens `http://127.0.0.1:5050` in your browser automatically.

## First-time setup in the dashboard

Go to **Settings** and paste in whichever of these you have:
- **OpenAI** key — platform.openai.com/api-keys
- **Gemini** key — aistudio.google.com/apikey
- **Claude** key — console.anthropic.com

Keys are saved to `config.json` in this folder only — never sent anywhere
except the provider you pick for a given action. Don't commit or share this
file.

## Real search-volume data (the easy way)

Three sources on the **Real search data** tab — no OAuth, just an API key:

- **Keywords Everywhere** — real Google-Keyword-Planner-sourced volume, CPC,
  competition, trend. Pay-as-you-go credits, sign up at
  keywordseverywhere.com and paste the key into Settings.
- **Semrush** — volume, CPC, competition, keyword difficulty. Uses your
  existing Semrush account's API key (Profile -> API). Batches up to 100
  keywords per call.
- **Google Trends** — completely free, no key. Gives *relative* interest
  (0-100 over the last 12 months), not an absolute search count. It's an
  unofficial API (via `pytrends`, which scrapes the public Trends UI), so
  Google can rate-limit or block it if you hit it too often — space out
  large batches.

This covers the same "how many people search this" question the Google Ads
tab answers, without the developer-token/OAuth setup below. Use the Google
Ads tab only if you specifically need Keyword Planner's own numbers or
already have API access set up for other reasons.

## Google Ads (advanced — real search-volume data via the official API)

This is the one tool that needs real Google-side setup first — it's not
something any app can self-serve:
1. Apply for a **Developer Token** in your Google Ads account (Tools ->
   API Center). A "test account" token only returns data for test accounts,
   not real numbers — you need it approved for production access.
2. Create an **OAuth Client ID + Secret** in Google Cloud Console
   (APIs & Services -> Credentials -> OAuth client ID -> Desktop app).
3. Generate a **Refresh Token** once, using that client ID/secret, via
   Google's OAuth desktop flow (search "google-ads-python generate_user_credentials"
   for the official script — it's a one-time terminal step that opens a
   browser to consent, then prints the refresh token).
4. Your **Customer ID** is the 10-digit ID of the Ads account you're calling
   from (top right of the Google Ads UI).

Paste all four plus your Customer ID into Settings, then use the **Google
Ads** tab.

`google_ads_tools.py` targets a recent `google-ads` library version. If a
call fails with an `AttributeError`, run `pip show google-ads` and check that
version's migration guide — Google revises this API's Python surface fairly
often.

## Notes on the other tools

- **Clean & merge**: handles 1000+ row exports — it batches 300 keywords per
  AI call automatically.
- **Generate**: for a target of 500+, it runs several batches under different
  keyword "angles" (informational, commercial, local, long-tail, etc.) and
  dedupes the results — better variety than asking for 500 in one shot.
- **Competitor sitemap**: reads `robots.txt` for the sitemap location (falls
  back to `/sitemap.xml`), follows one level of sitemap-index nesting, turns
  URL slugs into phrases, samples ~40 page titles, then asks the AI to
  synthesize a clean keyword list from that material. Very large sites are
  capped at 800 URLs to keep it fast.
