"""Record schema for one researched app.

Every researched claim is a `Claim`: a value plus the evidence (URL + verbatim
quote) it came from. Verification works on claims, so each one can be scored on
its own: grounded or not, and right or wrong against the human label.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

AuthMethod = Literal["oauth2", "api_key", "basic", "bearer_token", "jwt", "session_login", "none", "other"]
AccessTier = Literal[
    "self_serve_free",   # anyone can sign up and get credentials at no cost
    "self_serve_trial",  # self-serve, but only during a free trial
    "paid_plan",         # credentials need a paid subscription / plan tier
    "admin_approval",    # needs app review / admin approval / developer application
    "partner_gated",     # partnership program or invite only
    "contact_sales",     # API access only via sales
    "unknown",
]
Delivery = Literal["hosted_api", "mcp_only", "local_cli", "oss_library", "no_public_api"]
ApiStyle = Literal["rest", "graphql", "soap", "rpc", "websocket", "sdk_only", "none"]
Breadth = Literal["narrow", "medium", "broad", "unknown"]
Buildability = Literal["ready", "ready_with_friction", "blocked"]
Blocker = Literal[
    "none",
    "paid_plan_required",
    "partner_or_sales_gate",
    "app_review_or_approval",
    "no_public_api",
    "enterprise_only",
    "local_only_tool",
    "unclear_docs",
    "other",
]

FIELDS = [
    "one_liner",
    "auth_methods",
    "access_tier",
    "delivery",
    "api_styles",
    "api_breadth",
    "openapi_spec",
    "official_mcp",
    "buildability",
    "main_blocker",
]


class Evidence(BaseModel):
    url: str
    quote: str = Field(description="verbatim text copied from the page that supports the value")


class Claim(BaseModel):
    value: object
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    # filled in by the verification loops
    grounded: Optional[bool] = None
    flags: list[str] = Field(default_factory=list)


class AppRecord(BaseModel):
    n: int
    id: str
    name: str
    category: str
    hint: str
    docs_url: Optional[str] = None
    one_liner: Claim
    auth_methods: Claim          # list[AuthMethod]
    access_tier: Claim           # AccessTier
    delivery: Claim              # Delivery
    api_styles: Claim            # list[ApiStyle]
    api_breadth: Claim           # Breadth (+ rough resource count in notes)
    openapi_spec: Claim          # bool | "unknown"
    official_mcp: Claim          # bool | "unknown"; registry check overrides model output
    community_mcp: Optional[Claim] = None
    in_composio: Optional[bool] = None  # from Composio's own toolkit catalogue, not the model
    webhooks: Optional[Claim] = None
    sandbox: Optional[Claim] = None
    buildability: Claim          # Buildability
    main_blocker: Claim          # Blocker
    notes: str = ""
    needs_human: bool = False
    pass_name: str = "pass1"
    sources: list[str] = Field(default_factory=list)  # every URL the agent read
