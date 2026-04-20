import streamlit as st

from app.core import require_supabase, init_session_state, login, logout, refresh_role, signup
from app.core import get_supabase, init_session_state, login, logout, refresh_role, signup
from app.ui import inject_design_system

st.set_page_config(page_title="Curtain ERP", page_icon="🪟", layout="wide")
inject_design_system()
init_session_state()
sb = require_supabase()
sb = get_supabase()

st.title("🪟 Curtain ERP")
st.caption("Production-ready ERP + POS on Streamlit + Supabase")

if st.session_state.get("user"):
    refresh_role(sb)

with st.sidebar:
    st.markdown("### Duka ERP")
    if st.session_state.get("user"):
        st.write(f"**{st.session_state['user'].email}**")
        st.write(f"Role: `{st.session_state['role']}`")
        st.page_link("main.py", label="Home")
        st.page_link("pages/1_POS.py", label="POS")
        st.page_link("pages/2_Inventory.py", label="Inventory")
        st.page_link("pages/3_Finance.py", label="Finance")
        st.page_link("pages/4_Orders.py", label="Orders")
        st.page_link("pages/5_Admin.py", label="Admin")
        if st.button("Logout"):
            logout(sb)
            st.rerun()
    else:
        st.info("Please login or signup")

if not st.session_state.get("user"):
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Login")
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit_login = st.form_submit_button("Login")
            if submit_login:
                ok, msg = login(sb, email, password)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.rerun()

    with c2:
        st.subheader("Signup")
        with st.form("signup_form"):
            new_email = st.text_input("Email", key="su_email")
            new_password = st.text_input("Password", type="password", key="su_pw")
            submit_signup = st.form_submit_button("Create Account")
            if submit_signup:
                ok, msg = signup(sb, new_email, new_password)
                (st.success if ok else st.error)(msg)

    st.stop()

st.success("Authentication active. Use the sidebar to navigate modules.")

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Current Role", st.session_state["role"])
with c2:
    st.metric("Cart Items", len(st.session_state["cart"]))
with c3:
    st.metric("Auth Status", "Active")

st.markdown(
    """
    ### Access Rules
    - POS: all users
    - Inventory: all users (editing restricted)
    - Finance: admin only
    - Admin page: admin only
    """
)
