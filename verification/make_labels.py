"""Reference labels for the 20-app review sample, written from live vendor pages (checked 2026-11-23).

Who labelled: the AI assistant, reading official docs (page readers + browser + live URL checks),
independently of the agent's pages, then reconciling with the agent's cited evidence only after
re-fetching that evidence live. The user audits a random subset (column `audit`).

Label semantics
  value fields : `ok` = list of acceptable values (more than one when the docs genuinely support both)
  list fields  : `req` must all be predicted, nothing outside `req`+`allow` may be predicted
  one_liner    : `ok` = ["accurate"] -> judged on the predicted text
  status=skip  : could not be verified from the vendor's site; excluded from scoring

python -m verification.make_labels   -> verification/human_labels.csv
"""
import csv

from research import config

L = {}


def lab(app, field, ok=None, req=None, allow=None, url="", note="", status="labeled"):
    L.setdefault(app, {})[field] = dict(ok=ok or [], req=req or [], allow=allow or [], url=url, note=note, status=status)


A = "accurate"
# 92 Otter AI
lab("otter-ai", "one_liner", [A])
lab("otter-ai", "auth_methods", req=["api_key"], allow=["bearer_token", "oauth2"], url="https://help.otter.ai/hc/en-us/articles/36130822688279", note="API key sent as Bearer; OAuth only for the MCP server")
lab("otter-ai", "access_tier", ["contact_sales", "paid_plan"], url="https://help.otter.ai/hc/en-us/articles/36130822688279", note="'available for all Enterprise workspaces'; contact account manager")
lab("otter-ai", "delivery", ["hosted_api"], url="https://help.otter.ai/hc/en-us/articles/36130822688279")
lab("otter-ai", "api_styles", req=["rest"], url="https://help.otter.ai/hc/en-us/articles/36130822688279")
lab("otter-ai", "api_breadth", ["narrow", "medium"], url="https://help.otter.ai/hc/en-us/articles/36130822688279", note="~8 resource types (channels, conversations, transcripts, audio, action items, insights, outlines, workspace)")
lab("otter-ai", "openapi_spec", [False], url="https://help.otter.ai/hc/en-us/articles/36130822688279", note="no spec found")
lab("otter-ai", "official_mcp", [True], url="https://help.otter.ai/hc/en-us/articles/35287607569687-Otter-MCP-Server")
lab("otter-ai", "buildability", ["blocked"], note="enterprise-only API")
lab("otter-ai", "main_blocker", ["enterprise_only", "partner_or_sales_gate", "paid_plan_required"])
# 99 TranscriptAPI
lab("youtube-transcript", "one_liner", [A])
lab("youtube-transcript", "auth_methods", req=["api_key"], allow=["bearer_token", "oauth2"], url="https://transcriptapi.com/docs/api", note="'Bearer token authentication' with API key; OAuth 2.1 only for MCP")
lab("youtube-transcript", "access_tier", ["self_serve_free"], url="https://transcriptapi.com/docs/mcp/", note="100 free credits, no card")
lab("youtube-transcript", "delivery", ["hosted_api"], url="https://transcriptapi.com/docs/api")
lab("youtube-transcript", "api_styles", req=["rest"], url="https://transcriptapi.com/docs/api")
lab("youtube-transcript", "api_breadth", ["medium"], url="https://transcriptapi.com/docs/api", note="13 endpoints listed")
lab("youtube-transcript", "openapi_spec", [True], url="https://transcriptapi.com/openapi.json")
lab("youtube-transcript", "official_mcp", [True], url="https://transcriptapi.com/docs/mcp/")
lab("youtube-transcript", "buildability", ["ready"])
lab("youtube-transcript", "main_blocker", ["none"])
# 9 Copper
lab("copper", "one_liner", [A])
lab("copper", "auth_methods", req=["api_key", "oauth2"], url="https://developer.copper.com/introduction/authentication.html")
lab("copper", "access_tier", ["self_serve_trial", "paid_plan"], url="https://www.copper.com/pricing", note="free trial, no permanent free plan")
lab("copper", "delivery", ["hosted_api"], url="https://developer.copper.com")
lab("copper", "api_styles", req=["rest"], url="https://developer.copper.com")
lab("copper", "api_breadth", ["medium", "broad"], url="https://developer.copper.com", note="14 resource groups, ~90 operation pages")
lab("copper", "openapi_spec", [False], url="https://developer.copper.com", note="Postman collection only")
lab("copper", "official_mcp", [True], url="https://www.copper.com/mcp", note="'Copper's official MCP server' (beta Nov 2026)")
lab("copper", "buildability", ["ready_with_friction", "blocked"], note="buildable in trial, paid plan after")
lab("copper", "main_blocker", ["paid_plan_required"])
# 7 Zoho CRM
lab("zoho-crm", "one_liner", [A])
lab("zoho-crm", "auth_methods", req=["oauth2"], allow=["bearer_token"], url="https://www.zoho.com/crm/developer/docs/api/v8/oauth-overview.html")
lab("zoho-crm", "access_tier", ["self_serve_free"], url="https://www.zoho.com/crm/developer/docs/api/v8/api-limits.html", note="Free Edition 5000 credits/day; open Developer Console")
lab("zoho-crm", "delivery", ["hosted_api"])
lab("zoho-crm", "api_styles", req=["rest"], allow=["graphql"], url="https://www.zoho.com/crm/developer/docs")
lab("zoho-crm", "api_breadth", ["broad"], url="https://www.zoho.com/crm/developer/docs/api/v8/api-limits.html")
lab("zoho-crm", "openapi_spec", [False], note="no spec found")
lab("zoho-crm", "official_mcp", [True], url="https://www.zoho.com/crm/developer/docs/mcp/overview.html")
lab("zoho-crm", "buildability", ["ready", "ready_with_friction"], note="per-data-centre base URLs, credit limits")
lab("zoho-crm", "main_blocker", ["none", "other"])
# 26 Discord
lab("discord", "one_liner", [A])
lab("discord", "auth_methods", req=["oauth2", "api_key"], allow=["bearer_token", "basic"], url="https://docs.discord.com/developers/reference", note="bot token (static) + OAuth2 bearer; Basic only on token endpoints")
lab("discord", "access_tier", ["self_serve_free"], url="https://docs.discord.com/developers/reference")
lab("discord", "delivery", ["hosted_api"])
lab("discord", "api_styles", req=["rest"], allow=["websocket"], url="https://docs.discord.com/developers/reference")
lab("discord", "api_breadth", ["broad"])
lab("discord", "openapi_spec", [True], url="https://github.com/discord/discord-api-spec")
lab("discord", "official_mcp", [False], note="none found on vendor docs")
lab("discord", "buildability", ["ready", "ready_with_friction"], note="privileged intents / some scopes need review")
lab("discord", "main_blocker", ["none", "app_review_or_approval"])
# 28 WhatsApp Business
lab("whatsapp-business", "one_liner", [A])
lab("whatsapp-business", "auth_methods", req=["bearer_token"], allow=["oauth2", "api_key"], url="https://developers.facebook.com/docs/whatsapp/access-tokens")
lab("whatsapp-business", "access_tier", ["self_serve_free", "admin_approval"], url="https://developers.facebook.com/docs/whatsapp/cloud-api/get-started", note="test number free; App Review/verification for production")
lab("whatsapp-business", "delivery", ["hosted_api"])
lab("whatsapp-business", "api_styles", req=["rest"])
lab("whatsapp-business", "api_breadth", ["medium", "broad"])
lab("whatsapp-business", "openapi_spec", [True], url="https://github.com/meta/openapi")
lab("whatsapp-business", "official_mcp", [True], url="https://developers.facebook.com/documentation/mcp/whatsapp-business-tools-mcp")
lab("whatsapp-business", "buildability", ["ready_with_friction"])
lab("whatsapp-business", "main_blocker", ["app_review_or_approval"])
# 54 MrScraper
lab("mrscraper", "one_liner", [A])
lab("mrscraper", "auth_methods", req=["api_key"], allow=["bearer_token", "oauth2"], url="https://docs.mrscraper.com/docs/api/overview", note="x-api-token header; OAuth 2.1 for MCP")
lab("mrscraper", "access_tier", ["self_serve_free", "paid_plan"], url="https://mrscraper.com/pricing", note="Free plan exists; API on free not stated")
lab("mrscraper", "delivery", ["hosted_api"])
lab("mrscraper", "api_styles", req=["rest"])
lab("mrscraper", "api_breadth", ["narrow", "medium"], note="~11 operations")
lab("mrscraper", "openapi_spec", [False], note="no spec found")
lab("mrscraper", "official_mcp", [True], url="https://docs.mrscraper.com/docs/getting-started/mcp-server")
lab("mrscraper", "buildability", ["ready", "ready_with_friction"])
lab("mrscraper", "main_blocker", ["none", "paid_plan_required"])
# 58 Sherlock
lab("sherlock", "one_liner", [A])
lab("sherlock", "auth_methods", req=["none"], url="https://github.com/sherlock-project/sherlock")
lab("sherlock", "access_tier", ["self_serve_free"], note="MIT open source")
lab("sherlock", "delivery", ["local_cli", "oss_library"], url="https://github.com/sherlock-project/sherlock")
lab("sherlock", "api_styles", allow=["none", "rest"], url="https://github.com/sherlock-project/api", note="CLI; separate self-hosted DRF REST API project exists")
lab("sherlock", "api_breadth", ["narrow"])
lab("sherlock", "openapi_spec", [False])
lab("sherlock", "official_mcp", [False])
lab("sherlock", "buildability", ["ready_with_friction", "blocked"], note="local tool, no hosted API")
lab("sherlock", "main_blocker", ["local_only_tool", "no_public_api"])
# 61 GitHub
lab("github", "one_liner", [A])
lab("github", "auth_methods", req=["oauth2", "api_key"], allow=["bearer_token", "basic", "jwt"], url="https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api")
lab("github", "access_tier", ["self_serve_free"])
lab("github", "delivery", ["hosted_api"])
lab("github", "api_styles", req=["rest"], allow=["graphql"])
lab("github", "api_breadth", ["broad"])
lab("github", "openapi_spec", [True], url="https://github.com/github/rest-api-description")
lab("github", "official_mcp", [True], url="https://github.com/github/github-mcp-server")
lab("github", "buildability", ["ready"])
lab("github", "main_blocker", ["none"])
# 70 Sentry
lab("sentry", "one_liner", [A])
lab("sentry", "auth_methods", req=["oauth2", "bearer_token"], allow=["api_key", "basic"], url="https://docs.sentry.io/api/auth/")
lab("sentry", "access_tier", ["paid_plan", "self_serve_trial"], url="https://sentry.io/pricing/", note="Developer (free) plan table: 'API | No'; Team plan first with API")
lab("sentry", "delivery", ["hosted_api"])
lab("sentry", "api_styles", req=["rest"])
lab("sentry", "api_breadth", ["broad"])
lab("sentry", "openapi_spec", [True], url="https://github.com/getsentry/sentry-api-schema")
lab("sentry", "official_mcp", [True], url="https://mcp.sentry.dev/")
lab("sentry", "buildability", ["ready_with_friction", "blocked"], note="API needs Team plan")
lab("sentry", "main_blocker", ["paid_plan_required"])
# 49 Amazon Selling Partner
lab("amazon-selling-partner", "one_liner", [A])
lab("amazon-selling-partner", "auth_methods", req=["oauth2"], allow=["bearer_token"], url="https://developer-docs.amazon.com/sp-api/docs/connecting-to-the-selling-partner-api", note="Login with Amazon (LWA) tokens; RDT for PII")
lab("amazon-selling-partner", "access_tier", ["admin_approval", "paid_plan", "partner_gated"], url="https://developer.amazonservices.com/start/getting-started-for-private-developers", note="'Only Professional Selling Accounts can register'; developer profile reviewed")
lab("amazon-selling-partner", "delivery", ["hosted_api"])
lab("amazon-selling-partner", "api_styles", req=["rest"])
lab("amazon-selling-partner", "api_breadth", ["broad"])
lab("amazon-selling-partner", "openapi_spec", [True], url="https://github.com/amzn/selling-partner-api-models")
lab("amazon-selling-partner", "official_mcp", [False], note="none found on vendor docs")
lab("amazon-selling-partner", "buildability", ["ready_with_friction", "blocked"])
lab("amazon-selling-partner", "main_blocker", ["app_review_or_approval", "paid_plan_required", "partner_or_sales_gate"])
# 43 BigCommerce
lab("bigcommerce", "one_liner", [A])
lab("bigcommerce", "auth_methods", req=["api_key", "oauth2"], allow=["jwt", "basic", "bearer_token", "none"], url="https://docs.bigcommerce.com/docs/start/authentication", note="X-Auth-Token access tokens, OAuth grant flow, JWT, legacy Basic")
lab("bigcommerce", "access_tier", ["self_serve_trial", "paid_plan", "partner_gated"], note="needs a store (trial/paid); sandbox via Partner Portal")
lab("bigcommerce", "delivery", ["hosted_api"])
lab("bigcommerce", "api_styles", req=["rest", "graphql"], url="https://docs.bigcommerce.com/docs/start/authentication")
lab("bigcommerce", "api_breadth", ["broad"])
lab("bigcommerce", "openapi_spec", [True], url="https://docs.bigcommerce.com", note="'import our API specification files ... Open API'")
lab("bigcommerce", "official_mcp", [True], url="https://docs.bigcommerce.com/developer/api-reference/mcp/overview")
lab("bigcommerce", "buildability", ["ready_with_friction"])
lab("bigcommerce", "main_blocker", ["paid_plan_required", "partner_or_sales_gate"])
# 88 Brex
lab("brex", "one_liner", [A])
lab("brex", "auth_methods", req=["bearer_token"], allow=["api_key", "oauth2"], url="https://developer.brex.com/docs/authentication/", note="user token as Bearer; OAuth for MCP clients")
lab("brex", "access_tier", ["admin_approval", "self_serve_free"], url="https://www.brex.com/pricing", note="API on $0 Essentials, but needs an approved Brex company account; production only")
lab("brex", "delivery", ["hosted_api"])
lab("brex", "api_styles", req=["rest"])
lab("brex", "api_breadth", ["medium", "broad"], note="10 API groups")
lab("brex", "openapi_spec", [True], url="https://developer.brex.com", note="'defined using the OpenAPI specification'")
lab("brex", "official_mcp", [True], url="https://developer.brex.com/docs/mcp")
lab("brex", "buildability", ["ready", "ready_with_friction"])
lab("brex", "main_blocker", ["none", "other", "app_review_or_approval"])
# 86 QuickBooks
lab("quickbooks", "one_liner", [A])
lab("quickbooks", "auth_methods", req=["oauth2"], allow=["bearer_token"], url="https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization/oauth-2.0")
lab("quickbooks", "access_tier", ["self_serve_free", "admin_approval"], url="https://static.developer.intuit.com/resources/Intuit_App_Partner_Program_Guide.pdf", note="Builder tier no fees; sandbox companies; production keys need app assessment")
lab("quickbooks", "delivery", ["hosted_api"])
lab("quickbooks", "api_styles", req=["rest"], allow=["graphql"])
lab("quickbooks", "api_breadth", ["broad"])
lab("quickbooks", "openapi_spec", [False], note="no spec found")
lab("quickbooks", "official_mcp", [True], url="https://github.com/intuit/quickbooks-online-mcp-server")
lab("quickbooks", "buildability", ["ready_with_friction"])
lab("quickbooks", "main_blocker", ["app_review_or_approval", "other"])
# 31 Google Ads
lab("google-ads", "one_liner", [A])
lab("google-ads", "auth_methods", req=["oauth2"], allow=["bearer_token"], url="https://developers.google.com/google-ads/api/docs/api-policy/access-levels", note="developer tokens sunset 2026-09-09")
lab("google-ads", "access_tier", ["self_serve_free", "admin_approval"], url="https://developers.google.com/google-ads/api/docs/api-policy/access-levels", note="Test access immediate; Basic/Standard need review")
lab("google-ads", "delivery", ["hosted_api"])
lab("google-ads", "api_styles", req=["rest"], allow=["rpc"])
lab("google-ads", "api_breadth", ["broad"])
lab("google-ads", "openapi_spec", [False], note="discovery document, not OpenAPI")
lab("google-ads", "official_mcp", [True], url="https://developers.google.com/google-ads/api/docs/developer-toolkit/mcp-server")
lab("google-ads", "buildability", ["ready_with_friction"])
lab("google-ads", "main_blocker", ["app_review_or_approval"])
# 35 Mailchimp
lab("mailchimp", "one_liner", [A])
lab("mailchimp", "auth_methods", req=["oauth2", "api_key"], allow=["basic", "bearer_token"], url="https://mailchimp.com/developer/marketing/docs/fundamentals/")
lab("mailchimp", "access_tier", ["self_serve_free"], note="free account issues API keys; free-plan API scope not stated on pricing page")
lab("mailchimp", "delivery", ["hosted_api"])
lab("mailchimp", "api_styles", req=["rest"])
lab("mailchimp", "api_breadth", ["broad"])
lab("mailchimp", "openapi_spec", [True], url="https://mailchimp.com/developer/marketing/docs/fundamentals/")
lab("mailchimp", "official_mcp", [True], url="https://mailchimp.com/developer/transactional/guides/how-to-use-mailchimps-transactional-messaging-mcp")
lab("mailchimp", "buildability", ["ready", "ready_with_friction"])
lab("mailchimp", "main_blocker", ["none", "other"])
# 72 Airtable
lab("airtable", "one_liner", [A])
lab("airtable", "auth_methods", req=["api_key", "oauth2"], allow=["bearer_token"], url="https://airtable.com/developers/web/guides/personal-access-tokens")
lab("airtable", "access_tier", ["self_serve_free"], url="https://airtable.com/pricing")
lab("airtable", "delivery", ["hosted_api"])
lab("airtable", "api_styles", req=["rest"], url="https://airtable.com/developers/web/api/introduction", note="webhooks are HTTP callbacks, not WebSocket")
lab("airtable", "api_breadth", ["medium"])
lab("airtable", "openapi_spec", [False], note="no spec found")
lab("airtable", "official_mcp", [True], url="https://airtable.com/developers/agents/mcp/getting-started")
lab("airtable", "buildability", ["ready", "ready_with_friction"], note="free-plan API call caps")
lab("airtable", "main_blocker", ["none", "other", "paid_plan_required"])
# 80 Harvest
lab("harvest", "one_liner", [A])
lab("harvest", "auth_methods", req=["api_key", "oauth2"], allow=["bearer_token"], url="https://help.getharvest.com/api-v2/authentication-api/authentication/authentication/")
lab("harvest", "access_tier", ["self_serve_free", "self_serve_trial"], url="https://www.getharvest.com/pricing")
lab("harvest", "delivery", ["hosted_api"])
lab("harvest", "api_styles", req=["rest"])
lab("harvest", "api_breadth", ["broad"], note="~60 endpoint pages")
lab("harvest", "openapi_spec", [False], note="no spec found")
lab("harvest", "official_mcp", [True], url="https://support.getharvest.com/hc/en-us/articles/46293697226381-Harvest-MCP", note="vendor support page (403 to bots, text seen in agent's fetch)")
lab("harvest", "buildability", ["ready"])
lab("harvest", "main_blocker", ["none"])
# 12 Intercom
lab("intercom", "one_liner", [A])
lab("intercom", "auth_methods", req=["api_key", "oauth2"], allow=["bearer_token"], url="https://developers.intercom.com/docs/build-an-integration/learn-more/authentication")
lab("intercom", "access_tier", ["self_serve_trial", "paid_plan"], url="https://www.intercom.com/pricing", note="14-day trial, no free plan")
lab("intercom", "delivery", ["hosted_api"])
lab("intercom", "api_styles", req=["rest"])
lab("intercom", "api_breadth", ["broad"])
lab("intercom", "openapi_spec", [True], url="https://github.com/intercom/Intercom-OpenAPI")
lab("intercom", "official_mcp", [True], url="https://developers.intercom.com/docs/guides/mcp")
lab("intercom", "buildability", ["ready_with_friction", "blocked"])
lab("intercom", "main_blocker", ["paid_plan_required"])
# 17 Plain
lab("plain", "one_liner", [A])
lab("plain", "auth_methods", req=["api_key"], allow=["bearer_token", "oauth2"], url="https://www.plain.com/docs/graphql/authentication")
lab("plain", "access_tier", ["self_serve_trial", "paid_plan"], url="https://www.plain.com/pricing", note="7-day trial, no free plan")
lab("plain", "delivery", ["hosted_api"])
lab("plain", "api_styles", req=["graphql"], url="https://www.plain.com/docs/graphql/introduction")
lab("plain", "api_breadth", status="skip", note="schema size not verified")
lab("plain", "openapi_spec", [False], note="GraphQL schema, not OpenAPI")
lab("plain", "official_mcp", [True], url="https://www.plain.com/docs/integrations/mcp-server.md")
lab("plain", "buildability", ["ready_with_friction", "blocked"])
lab("plain", "main_blocker", ["paid_plan_required"])


# Independent audit by the user (2026-11-24) of 5 randomly drawn labels (seed 20261124): 5 of 5 agreed.
AUDIT = {("otter-ai", "delivery"), ("intercom", "auth_methods"), ("youtube-transcript", "buildability"),
         ("discord", "api_styles"), ("google-ads", "official_mcp")}


def main():
    out = config.ROOT / "verification" / "human_labels.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["app_id", "field", "status", "ok", "req", "allow", "evidence_url", "note", "labeler", "audit"])
        for app, fields in L.items():
            for field, d in fields.items():
                w.writerow([app, field, d["status"], "|".join(map(str, d["ok"])), "|".join(d["req"]), "|".join(d["allow"]),
                            d["url"], d["note"], "ai-assistant (live docs)",
                            "user: agree" if (app, field) in AUDIT else ""])
    print(f"wrote {sum(len(v) for v in L.values())} labels for {len(L)} apps -> {out}")


if __name__ == "__main__":
    main()
