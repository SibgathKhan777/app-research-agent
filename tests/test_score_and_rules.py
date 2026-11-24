from verification.auto_checks import _org_matches, check_rules
from verification.score import is_correct

AUTH = {"req": ["oauth2", "api_key"], "allow": ["bearer_token", "basic"], "ok": []}


def test_list_field_needs_all_required():
    assert is_correct("auth_methods", ["oauth2", "api_key"], AUTH)
    assert not is_correct("auth_methods", ["oauth2"], AUTH)


def test_list_field_allows_optional_but_not_extra():
    assert is_correct("auth_methods", ["oauth2", "api_key", "basic"], AUTH)
    assert not is_correct("auth_methods", ["oauth2", "api_key", "jwt"], AUTH)


def test_list_field_with_only_allowed_values():
    lab = {"req": [], "allow": ["none", "rest"], "ok": []}
    assert is_correct("api_styles", ["rest"], lab)
    assert not is_correct("api_styles", [], lab)


def test_unknown_is_a_miss():
    assert not is_correct("official_mcp", "unknown", {"ok": ["True"], "req": [], "allow": []})
    assert not is_correct("auth_methods", "unknown", AUTH)


def test_value_field_accepts_any_listed_value_and_bool_strings():
    lab = {"ok": ["self_serve_trial", "paid_plan"], "req": [], "allow": []}
    assert is_correct("access_tier", "paid_plan", lab)
    assert not is_correct("access_tier", "self_serve_free", lab)
    assert is_correct("openapi_spec", True, {"ok": ["True"], "req": [], "allow": []})


def test_changed_one_liner_needs_rejudging():
    lab = {"ok": ["accurate"], "req": [], "allow": []}
    assert is_correct("one_liner", "CRM", lab, pass1_pred="CRM")
    assert not is_correct("one_liner", "Something else", lab, pass1_pred="CRM")


def _rec(**v):
    base = dict(one_liner="x", auth_methods=["api_key"], access_tier="self_serve_free", delivery="hosted_api",
                api_styles=["rest"], api_breadth="medium", openapi_spec=False, official_mcp=False,
                buildability="ready", main_blocker="none")
    base.update(v)
    return {k: {"value": val, "evidence": []} for k, val in base.items()}


def test_rules_catch_contradictions():
    out = []
    check_rules(_rec(buildability="ready", main_blocker="paid_plan_required"), out)
    assert any(f["check"] == "rule" for f in out)
    out = []
    check_rules(_rec(access_tier="contact_sales", buildability="ready"), out)
    assert any(f["field"] == "buildability" for f in out)
    out = []
    check_rules(_rec(auth_methods=["none", "api_key"]), out)
    assert any(f["field"] == "auth_methods" for f in out)


def test_consistent_record_has_no_rule_flags():
    out = []
    check_rules(_rec(), out)
    assert out == []


def test_mcp_org_matching_is_strict():
    assert _org_matches("getsentry", {"sentry"})
    assert _org_matches("Snowflake-Labs", {"snowflake"})
    assert not _org_matches("princezoho", {"zoho"})
    assert not _org_matches("mcp-telegram", {"telegram"})
