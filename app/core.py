import os
from typing import Any

import streamlit as st
from supabase import Client, create_client


def _read_secret(name: str) -> str | None:
    return os.environ.get(name) or st.secrets.get(name)


@st.cache_resource
def get_supabase() -> Client | None:
    url = _read_secret("SUPABASE_URL")
    key = _read_secret("SUPABASE_KEY") or _read_secret("SUPABASE_ANON_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def require_supabase() -> Client:
    sb = get_supabase()
    if sb is None:
        st.error(
            "Supabase is not configured. Add `SUPABASE_URL` and `SUPABASE_KEY` "
            "(or `SUPABASE_ANON_KEY`) in Streamlit secrets or environment variables."
        )
        st.code(
            'SUPABASE_URL = "https://<project>.supabase.co"\n'
            'SUPABASE_KEY = "<anon-key>"',
            language="toml",
        )
        st.stop()
    return sb


def init_session_state() -> None:
    st.session_state.setdefault("session", None)
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("role", "cashier")
    st.session_state.setdefault("cart", [])


def refresh_role(sb: Client) -> str:
    user = st.session_state.get("user")
    if not user:
        st.session_state["role"] = "cashier"
        return "cashier"

    profile = sb.table("profiles").select("role").eq("id", user.id).limit(1).execute().data
    if not profile:
        sb.table("profiles").insert({"id": user.id, "email": user.email, "role": "cashier"}).execute()
        st.session_state["role"] = "cashier"
    else:
        st.session_state["role"] = profile[0].get("role", "cashier")
    return st.session_state["role"]


def require_auth() -> None:
    if not st.session_state.get("user"):
        st.warning("Please login first.")
        st.stop()


def require_admin() -> None:
    require_auth()
    if st.session_state.get("role") != "admin":
        st.error("Admin-only page")
        st.stop()


def login(sb: Client, email: str, password: str) -> tuple[bool, str]:
    try:
        response = sb.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state["session"] = response.session
        st.session_state["user"] = response.user
        refresh_role(sb)
        return True, "Logged in"
    except Exception as exc:
        return False, str(exc)


def signup(sb: Client, email: str, password: str) -> tuple[bool, str]:
    try:
        sb.auth.sign_up({"email": email, "password": password})
        return True, "Signup successful. Please check your email for confirmation if enabled."
    except Exception as exc:
        return False, str(exc)


def logout(sb: Client) -> None:
    sb.auth.sign_out()
    st.session_state["session"] = None
    st.session_state["user"] = None
    st.session_state["role"] = "cashier"
    st.session_state["cart"] = []


def log_audit(sb: Client, action: str, table_name: str, record_id: str, old_value: Any, new_value: Any) -> None:
    user = st.session_state.get("user")
    sb.table("audit_logs").insert(
        {
            "user_id": user.id if user else None,
            "action": action,
            "table_name": table_name,
            "record_id": str(record_id),
            "old_value": old_value,
            "new_value": new_value,
        }
    ).execute()


def safe_float(value: Any) -> float:
    return float(value or 0)
