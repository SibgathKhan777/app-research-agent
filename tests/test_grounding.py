from research.grounding import quote_in_page

PAGE = """Every Pipedrive plan comes with an API token that gives you access to our **RESTful API**.
| Method | Use |
| OAuth 2.0 | apps for many users |"""


def test_exact_quote_is_grounded():
    assert quote_in_page("Every Pipedrive plan comes with an API token", PAGE)


def test_markdown_and_case_are_ignored():
    assert quote_in_page("access to our RESTful API", PAGE)


def test_invented_quote_is_not_grounded():
    assert not quote_in_page("Pipedrive API access requires the Enterprise plan", PAGE)


def test_stitched_quote_needs_every_piece():
    assert quote_in_page("Every Pipedrive plan comes with an API token ... gives you access to our RESTful API", PAGE)
    assert not quote_in_page("Every Pipedrive plan comes with an API token ... only for enterprise customers today", PAGE)


def test_too_short_quote_is_not_grounded():
    assert not quote_in_page("API token", PAGE)


def test_smart_quotes_and_dashes_match():
    assert quote_in_page("HubSpot’s API endpoints are — public", "HubSpot's API endpoints are - public")
