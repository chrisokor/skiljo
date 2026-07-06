"""Review page — skill viewer, version selector, and approve functionality."""

import requests
import streamlit as st

from api_client import approve_version, get_skill_versions, list_skills

st.title("Review and Approve Skill")

# Fetch all skills
try:
    skills = list_skills()
except requests.HTTPError as exc:
    st.error(f"Failed to load skills: {exc}")
    st.stop()
except requests.ConnectionError:
    st.error("Cannot reach API. Is the server running?")
    st.stop()

if not skills:
    st.info("No skills found. Go to **Extract** to create one.")
    st.stop()

skill_names = [s["name"] for s in skills]
selected_skill_name = st.selectbox("Select skill:", skill_names)
skill = next(s for s in skills if s["name"] == selected_skill_name)

# Fetch versions for the selected skill
try:
    versions = get_skill_versions(skill["id"])
except requests.HTTPError as exc:
    st.error(f"Failed to load versions: {exc}")
    st.stop()

st.write(f"**Skill:** {skill['name']}")
st.write(f"**Total versions:** {len(versions)}")

# Show draft versions awaiting approval
draft_versions = [v for v in versions if v["status"] == "draft"]
if draft_versions:
    st.subheader("Draft Versions (Pending Approval)")
    for v in draft_versions:
        with st.expander(f"v{v['version_number']} — draft", expanded=True):
            st.json(v["spec"])
            if st.button(f"Approve v{v['version_number']}", key=f"approve_{v['id']}"):
                try:
                    approve_version(skill["id"], v["id"])
                    st.success(f"Version {v['version_number']} approved!")
                    st.rerun()
                except requests.HTTPError as exc:
                    st.error(f"Approve failed: {exc}")
else:
    st.info("No draft versions pending approval.")

# Show approved versions
approved_versions = [v for v in versions if v["status"] == "approved"]
if approved_versions:
    st.subheader("Approved Versions")
    for v in approved_versions:
        with st.expander(f"v{v['version_number']} — approved"):
            st.json(v["spec"])
