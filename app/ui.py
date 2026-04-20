import streamlit as st


def inject_design_system() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600&family=DM+Sans:wght@300;400;500&display=swap');

        :root {
            --bg: #0c0b09;
            --surface: #141210;
            --surface-2: #1c1916;
            --gold: #c8922a;
            --gold-dim: rgba(200,146,42,0.15);
            --text: #f0ead8;
            --muted: #9a8f7a;
            --border: rgba(240,234,216,0.10);
        }

        .stApp {
            background: var(--bg);
            color: var(--text);
            font-family: 'DM Sans', sans-serif;
        }

        [data-testid='stSidebar'] {
            background: var(--surface);
            border-right: 1px solid var(--border);
        }

        h1, h2, h3 {
            font-family: 'Cormorant Garamond', serif;
            color: var(--gold) !important;
            letter-spacing: 0.02em;
        }

        .panel {
            border: 1px solid var(--border);
            background: var(--surface-2);
            border-radius: 10px;
            padding: 14px;
            margin-bottom: 14px;
        }

        .gold-label {
            text-transform: uppercase;
            letter-spacing: .08em;
            color: var(--muted);
            font-size: 12px;
        }

        div[data-testid='stMetric'] {
            background: var(--surface-2);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 10px;
        }

        .stButton button, .stDownloadButton button {
            background: var(--gold) !important;
            color: #0c0b09 !important;
            border: none !important;
            border-radius: 6px !important;
            font-weight: 600 !important;
        }

        .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb='select'] > div {
            background: #232018 !important;
            color: var(--text) !important;
            border-color: var(--border) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def panel(title: str, subtitle: str | None = None) -> None:
    text = f"<div class='panel'><div class='gold-label'>{title}</div>"
    if subtitle:
        text += f"<div>{subtitle}</div>"
    text += "</div>"
    st.markdown(text, unsafe_allow_html=True)
