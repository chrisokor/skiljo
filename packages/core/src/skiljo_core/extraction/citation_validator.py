from skiljo_core.schemas.rule_schema import Citation


def validate_citation(citation: Citation, source_text: str) -> bool:
    """Validate that a citation's span and quoted text match its source text."""
    start, end = citation.span.start, citation.span.end

    if start < 0 or end > len(source_text):
        raise ValueError(
            f"Citation span [{start}, {end}) out of bounds for source text "
            f"(length {len(source_text)})"
        )

    if start >= end:
        raise ValueError(f"Citation span start ({start}) >= end ({end})")

    actual_text = source_text[start:end]
    if actual_text != citation.quoted_text:
        raise ValueError(
            "Citation quoted_text mismatch:\n"
            f"  Expected: {citation.quoted_text!r}\n"
            f"  Actual:   {actual_text!r}\n"
            f"  Span:     [{start}, {end})"
        )

    return True
