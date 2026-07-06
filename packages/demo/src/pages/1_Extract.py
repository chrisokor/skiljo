"""Extract page — upload policy text and extract a skill via the API."""

import sys
import time

import streamlit as st

# api_client lives one level up in src/; add it to path when running via `streamlit run pages/`.
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from api_client import extract_skill, get_job, get_skill_version, list_skills  # noqa: E402

st.title("Extract Policy into Skill")

# --- Input section ---
input_method = st.radio("Input method:", ["Paste text", "Upload file"])

policy_text = ""
if input_method == "Paste text":
    policy_text = st.text_area("Paste policy text:", height=300)
else:
    uploaded_file = st.file_uploader("Upload policy text file (.txt)", type=["txt"])
    if uploaded_file:
        policy_text = uploaded_file.read().decode("utf-8")

skill_name = st.text_input("Skill name:", value="extracted_policy_v1")
trigger = st.text_input(
    "Trigger (decision surface this skill governs):",
    value="refund_request",
    help="Examples: refund_request, credit_dispute, billing_adjustment",
)

# --- Submit ---
if st.button("Extract Skill", type="primary"):
    if not policy_text.strip():
        st.error("Policy text is required.")
    elif not skill_name.strip():
        st.error("Skill name is required.")
    else:
        with st.spinner("Submitting extraction job..."):
            try:
                job_id = extract_skill(policy_text, skill_name.strip(), trigger.strip())
            except Exception as exc:
                st.error(f"Failed to start extraction: {exc}")
                st.stop()

        st.success(f"Extraction job started (job_id: `{job_id}`)")

        # Poll until complete or failed (60-second timeout)
        progress = st.progress(0, text="Waiting for extraction...")
        job: dict = {}
        timed_out = True
        for i in range(60):
            try:
                job = get_job(job_id)
            except Exception as exc:
                st.error(f"Error polling job: {exc}")
                st.stop()

            status = job.get("status", "pending")
            progress.progress(min(i + 1, 59) / 59, text=f"Status: {status} ({i + 1}s)")

            if status == "completed":
                timed_out = False
                break
            elif status == "failed":
                progress.empty()
                st.error(f"Extraction failed: {job.get('error', 'unknown error')}")
                st.stop()

            time.sleep(1)

        if timed_out:
            progress.empty()
            st.error("Extraction timed out after 60 seconds. Check job status manually.")
            st.stop()

        progress.empty()

        # Retrieve and display result
        result_ref = job.get("result_ref")
        if result_ref:
            st.success("Skill extracted successfully!")
            try:
                # result_ref is the skill_version id; we need the skill_id from the version list
                # Use list_skills to find the skill that owns this version
                skills = list_skills()
                skill_row = next(
                    (s for s in skills if str(s.get("current_version_id")) == str(result_ref)),
                    None,
                )
                if skill_row:
                    skill_id = str(skill_row["id"])
                    version = get_skill_version(skill_id, str(result_ref))
                    st.subheader(f"Skill: {skill_row['name']}")
                    st.caption(
                        f"Version ID: `{result_ref}` · Status: **{version.get('status', 'draft')}**"
                    )
                    st.json(version.get("spec", {}))
                    st.info("Next: Go to **Review** to approve this skill.")
                else:
                    st.warning("Skill created but could not locate it in the skills list.")
                    st.json(job)
            except Exception as exc:
                st.warning(f"Extraction succeeded but could not fetch skill details: {exc}")
                st.json(job)
        else:
            st.warning("Job completed but no result_ref returned.")
            st.json(job)
