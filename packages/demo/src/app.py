import streamlit as st

st.set_page_config(page_title="Skiljo Demo", layout="wide")

st.sidebar.title("Skiljo Policy Skill Engine")
st.sidebar.markdown("""
Extract refund and credit policies into executable skills.
Simulate against historical tickets to detect contradictions.
""")

# Page navigation is automatic via pages/ directory structure
st.write("## Welcome to Skiljo")
st.write("Use the sidebar to navigate: Extract → Review → Simulate")
