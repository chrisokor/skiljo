"""Compare approved policy skills for cross-document contradictions."""
from __future__ import annotations

import json

import requests
import streamlit as st

from api_client import detect_cross_document_contradictions, get_skill_versions, list_skills

st.title("Cross-Document Contradictions")


def _approved_versions() -> list[tuple[dict, dict]]:
    """Return every approved version, paired with its skill summary."""
    pairs: list[tuple[dict, dict]] = []
    for skill in list_skills():
        try:
            versions = get_skill_versions(skill["id"])
        except requests.RequestException as exc:
            st.warning(f"Could not load versions for {skill['name']}: {exc}")
            continue
        pairs.extend((skill, version) for version in versions if version.get("status") == "approved")
    return pairs


def _rule_rows(spec: dict) -> list[dict[str, str]]:
    """Flatten a skill spec into display rows with its source citations."""
    rows: list[dict[str, str]] = []
    zones = spec.get("decision_zones", {})
    for zone in ("deterministic", "llm_assisted", "human_only"):
        for index, rule in enumerate(zones.get(zone, [])):
            citation = rule.get("citation", {})
            span = citation.get("span", {})
            rows.append(
                {
                    "Rule": f"{zone}[{index}]",
                    "Action": str(rule.get("action", "")),
                    "Condition": json.dumps(rule.get("condition", {}), sort_keys=True),
                    "Citation": (
                        f"{citation.get('quoted_text', '')} "
                        f"[{span.get('start', '?')}:{span.get('end', '?')}]"
                    ),
                }
            )
    return rows


try:
    approved_pairs = _approved_versions()
except requests.RequestException as exc:
    st.error(f"Could not reach API: {exc}")
    st.stop()
except Exception as exc:
    st.error(f"Could not load approved skills: {exc}")
    st.stop()

if len({str(skill["id"]) for skill, _ in approved_pairs}) < 2:
    st.info("Approve skill versions from at least two policies before comparing.")
    st.stop()

labels = [f"{skill['name']} (v{version['version_number']})" for skill, version in approved_pairs]
first_index = st.selectbox("Policy 1", range(len(approved_pairs)), format_func=labels.__getitem__)
first_skill, first_version = approved_pairs[first_index]
second_choices = [
    index for index, (skill, _) in enumerate(approved_pairs) if skill["id"] != first_skill["id"]
]
second_index = st.selectbox("Policy 2", second_choices, format_func=labels.__getitem__)

second_skill, second_version = approved_pairs[second_index]

left, right = st.columns(2)
with left:
    st.subheader(labels[first_index])
    st.dataframe(_rule_rows(first_version.get("spec", {})), use_container_width=True, hide_index=True)
with right:
    st.subheader(labels[second_index])
    st.dataframe(_rule_rows(second_version.get("spec", {})), use_container_width=True, hide_index=True)

if st.button("Detect Contradictions", type="primary"):
    try:
        with st.spinner("Detecting contradictions..."):
            contradictions = detect_cross_document_contradictions(
                [str(first_version["id"]), str(second_version["id"])]
            )
    except requests.HTTPError as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        st.error(f"Detection failed: {detail}")
        st.stop()
    except Exception as exc:
        st.error(f"Detection failed: {exc}")
        st.stop()

    if not contradictions:
        st.info("No contradictions detected.")
    else:
        st.subheader(f"Contradictions ({len(contradictions)})")
        for number, contradiction in enumerate(contradictions, start=1):
            with st.expander(
                f"{number}. {contradiction['action_1']} vs {contradiction['action_2']}",
                expanded=True,
            ):
                st.write(f"**Decision surface:** {contradiction['decision_surface']}")
                st.write(f"**{first_skill['name']}:** {contradiction['action_1']}")
                st.caption(
                    f"Citation: {contradiction['citation_1']['zone']}"
                    f"[{contradiction['citation_1']['rule_index']}]"
                )
                st.write(f"**{second_skill['name']}:** {contradiction['action_2']}")
                st.caption(
                    f"Citation: {contradiction['citation_2']['zone']}"
                    f"[{contradiction['citation_2']['rule_index']}]"
                )
                st.warning(contradiction["rationale"])
