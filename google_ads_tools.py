"""
Real Google Ads Keyword Planner data (search volume, competition, CPC bid ranges).

Requires the user to already have, from Google:
  - a Google Ads Developer Token (approved — "test account" tokens only work
    against test accounts, not real data)
  - an OAuth2 Client ID + Client Secret (Google Cloud Console)
  - a Refresh Token for that OAuth client, generated once via Google's
    OAuth desktop-app flow (see their google-ads-python docs — this is a
    one-time setup step outside this app)
  - a Google Ads Customer ID (the account the calls are billed/attributed to)

This is NOT something a browser-only tool can do — it needs these server-held
secrets. If any of this isn't set up yet, use the AI-generated keyword tab
instead; this tab lights up once google_ads config is filled in Settings.

NOTE: the google-ads library's API surface changes between major versions.
This targets a recent v1x client; if calls fail with an AttributeError,
check `pip show google-ads` and adjust per that version's migration guide.
"""

LANGUAGE_ENGLISH = "languageConstants/1000"  # English — see Google's language-constants list for others


def get_keyword_ideas(creds: dict, seed_keywords: list, geo_target_id: str = "2840", limit: int = 200):
    """
    creds: {developer_token, client_id, client_secret, refresh_token, login_customer_id}
    geo_target_id: Google Ads geo-target constant ID, default 2840 = United States.
    Returns: list of {keyword, avg_monthly_searches, competition, low_bid_micros, high_bid_micros}
    """
    from google.ads.googleads.client import GoogleAdsClient

    config = {
        "developer_token": creds["developer_token"],
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": creds["refresh_token"],
        "login_customer_id": creds.get("login_customer_id", "").replace("-", ""),
        "use_proto_plus": True,
    }
    client = GoogleAdsClient.load_from_dict(config)
    customer_id = creds["customer_id"].replace("-", "")

    keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")
    keyword_seed = client.get_type("KeywordSeed")
    keyword_seed.keywords.extend(seed_keywords)

    request = client.get_type("GenerateKeywordIdeasRequest")
    request.customer_id = customer_id
    request.language = LANGUAGE_ENGLISH
    request.geo_target_constants.append(f"geoTargetConstants/{geo_target_id}")
    request.keyword_plan_network = (
        client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH_AND_PARTNERS
    )
    request.keyword_seed = keyword_seed

    response = keyword_plan_idea_service.generate_keyword_ideas(request=request)

    results = []
    for idea in response:
        metrics = idea.keyword_idea_metrics
        results.append({
            "keyword": idea.text,
            "avg_monthly_searches": metrics.avg_monthly_searches,
            "competition": metrics.competition.name if metrics.competition else None,
            "low_bid_micros": metrics.low_top_of_page_bid_micros,
            "high_bid_micros": metrics.high_top_of_page_bid_micros,
        })
        if len(results) >= limit:
            break
    return results
