"""Presentation style-to-template integrity rules for Mini App payloads."""

from __future__ import annotations

from secrets import token_urlsafe
from typing import Any, Callable, Mapping

STYLE_TEMPLATE_NUMBERS: dict[str, frozenset[int]] = {
    "gold": frozenset(range(1, 35)),
    "silver": frozenset((35, 36)),
    "platinum": frozenset((37, 38)),
}


def issue_style_flow_tokens(
    token_factory: Callable[[int], str] = token_urlsafe,
) -> dict[str, str]:
    """Return one fresh per-conversation token per visible presentation style."""
    return {style: token_factory(16) for style in STYLE_TEMPLATE_NUMBERS}


def style_for_template(template_num: int) -> str | None:
    """Return the style that owns a template number, or ``None`` if unknown."""
    for style, templates in STYLE_TEMPLATE_NUMBERS.items():
        if template_num in templates:
            return style
    return None


def validate_style_template_payload(
    payload: Mapping[str, Any],
    issued_tokens: Mapping[str, str] | None,
) -> int | None:
    """Validate that a Mini App payload matches its issued style and template tier.

    The payload intentionally carries only non-sensitive routing metadata. A missing,
    stale, mismatched, or malformed token/template combination fails closed.
    """
    if not issued_tokens:
        return None

    style = payload.get("style_tier")
    flow_token = payload.get("style_flow")
    if not isinstance(style, str) or not isinstance(flow_token, str):
        return None
    if style not in STYLE_TEMPLATE_NUMBERS:
        return None
    if issued_tokens.get(style) != flow_token:
        return None

    try:
        template_num = int(payload.get("template_num"))
    except (TypeError, ValueError):
        return None

    return template_num if template_num in STYLE_TEMPLATE_NUMBERS[style] else None
