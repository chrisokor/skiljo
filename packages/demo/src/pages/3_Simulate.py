"""Simulate page — pick a skill version and ticket batch, run simulation, display report."""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests
import streamlit as st

from api_client import (
    create_simulation,
    get_job,
    get_simulation,
    get_simulation_report_html,
    get_skill_versions,
    list_skills,
    list_ticket_batches,
)

st.title("Run Simulation")

# ---------------------------------------------------------------------------
# 1. Skill selector — only skills that have at least one approved version
# ---------------------------------------------------------------------------
try:
    all_skills = list_skills()
except Exception as exc:
    st.error(f"Could not reach API: {exc}")
    st.stop()

# Collect (skill, approved_version) pairs
approved_pairs: list[tuple[dict, dict]] = []
for skill in all_skills:
    try:
        versions = get_skill_versions(skill["id"])
    except Exception:
        continue
    for v in versions:
        if v.get("status") == "approved":
            approved_pairs.append((skill, v))
            break  # one approved version per skill is enough to list it

if not approved_pairs:
    st.info("No approved skills found. Go to **Review** to approve a skill.")
    st.stop()

skill_labels = [f"{skill['name']} (v{ver['version_number']})" for skill, ver in approved_pairs]
selected_idx = st.selectbox("Select skill:", range(len(skill_labels)), format_func=lambda i: skill_labels[i])
selected_skill, selected_version = approved_pairs[selected_idx]

# ---------------------------------------------------------------------------
# 2. Ticket batch selector
# ---------------------------------------------------------------------------
batches = list_ticket_batches()
batch_labels = [b["name"] for b in batches]
selected_batch_idx = st.selectbox(
    "Select ticket batch:", range(len(batch_labels)), format_func=lambda i: batch_labels[i]
)
selected_batch = batches[selected_batch_idx]

# ---------------------------------------------------------------------------
# 3. Load tickets from disk for the selected batch
# ---------------------------------------------------------------------------
BATCH_PATHS: dict[str, Path] = {
    "refund_v1": Path(__file__).parents[3] / "data" / "synthetic_tickets" / "refund_v1" / "tickets.json",
}

batch_id = selected_batch["id"]
batch_path = BATCH_PATHS.get(batch_id)
if batch_path is None or not batch_path.exists():
    st.error(f"Ticket data not found for batch '{batch_id}'.")
    st.stop()

with open(batch_path) as f:
    tickets_raw: list[dict] = json.load(f)

st.caption(f"{len(tickets_raw)} tickets loaded from {batch_id}")

# ---------------------------------------------------------------------------
# 4. Run button
# ---------------------------------------------------------------------------
if st.button("Run Simulation", type="primary"):
    with st.spinner("Starting simulation..."):
        try:
            job_id = create_simulation(selected_version["id"], tickets_raw)
        except requests.HTTPError as exc:
            st.error(f"Failed to start simulation: {exc.response.text if exc.response else exc}")
            st.stop()
        except Exception as exc:
            st.error(f"Failed to start simulation: {exc}")
            st.stop()

    st.success(f"Simulation started (job {job_id})")

    # Poll job with progress bar, 120-second timeout
    progress = st.progress(0, text="Waiting for simulation to complete…")
    job: dict = {}
    for i in range(120):
        try:
            job = get_job(job_id)
        except Exception as exc:
            st.error(f"Error polling job: {exc}")
            st.stop()

        status = job.get("status", "pending")
        if status == "completed":
            progress.progress(100, text="Simulation complete.")
            break
        elif status == "failed":
            st.error(f"Simulation failed: {job.get('error', 'unknown error')}")
            st.stop()

        progress.progress(int((i + 1) / 120 * 90), text=f"Running… ({i + 1}s)")
        time.sleep(1)
    else:
        st.error("Simulation timed out after 120 seconds.")
        st.stop()

    # ---------------------------------------------------------------------------
    # 5. Fetch and display report
    # ---------------------------------------------------------------------------
    sim_id = job.get("result_ref")
    if not sim_id:
        st.error("Job completed but no simulation result reference found.")
        st.stop()

    try:
        sim_data = get_simulation(str(sim_id))
    except Exception as exc:
        st.error(f"Could not fetch simulation report: {exc}")
        st.stop()

    summary: dict = sim_data.get("summary") or {}

    st.success("Simulation completed!")

    # Summary metric cards
    col1, col2, col3, col4 = st.columns(4)
    match_rate = summary.get("match_rate", 0.0)
    escalation_accuracy = summary.get("escalation_accuracy", 0.0)
    contradiction_count = summary.get("contradiction_count") or 0
    automation_count = summary.get("automation_candidate_count") or 0

    col1.metric("Match Rate", f"{match_rate:.1%}")
    col2.metric("Escalation Accuracy", f"{escalation_accuracy:.1%}")
    col3.metric("Contradictions Found", contradiction_count)
    col4.metric("Automation Candidates", automation_count)

    # Contradiction note (detail view available in A5)
    if contradiction_count > 0:
        st.subheader("Contradictions Detected")
        st.info(
            f"{contradiction_count} contradiction cluster(s) detected. "
            "Detailed contradiction records with citations and financial impact will be available in the next release."
        )

    # Per-ticket results table
    results: list[dict] = summary.get("results", [])
    if results:
        st.subheader("Per-Ticket Results")
        table_rows = []
        for r in results:
            tid = str(r.get("ticket_id", ""))
            table_rows.append(
                {
                    "ticket_id": tid[:8] + "…" if len(tid) > 8 else tid,
                    "decision": r.get("decision", ""),
                    "zone": r.get("zone", ""),
                    "match": "✓" if r.get("matched_human_decision") else "✗",
                    "reasoning": (r.get("reasoning") or "")[:80],
                }
            )
        st.dataframe(table_rows, use_container_width=True)
    else:
        st.info("No per-ticket results available.")

    st.subheader("Report")
    try:
        report_html = get_simulation_report_html(str(sim_id))
    except Exception as exc:
        st.warning(f"Simulation completed, but the HTML report could not be loaded: {exc}")
    else:
        st.download_button(
            "Download HTML report",
            data=report_html,
            file_name=f"skiljo_simulation_{sim_id}.html",
            mime="text/html",
        )

st.divider()
st.markdown("[Cross-Document Detection](./Cross_Document)")
