import streamlit as st

st.set_page_config(page_title="Skiljo | Policy Consistency Checker", page_icon="S", layout="wide")

st.sidebar.title("Skiljo v1.05")
st.sidebar.caption("Policy consistency checker")
st.sidebar.divider()

st.title("Skiljo")
st.subheader("Policy consistency checker")
st.caption("Extract -> Review -> Simulate -> Compare")

if st.button("Extract policy", type="primary"):
    st.switch_page("pages/1_Extract.py")
