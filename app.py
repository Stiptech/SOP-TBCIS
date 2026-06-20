import os
import base64
from datetime import datetime, date
from pathlib import Path
from html import escape

import pandas as pd
import streamlit as st
from supabase import create_client


APP_TITLE = "TBCIS Admission Management System"
SCHOOL_NAME = "Terang Bangsa Cambridge International School"

LEAD_STATUSES = [
    "NEW_LEAD",
    "CONTACTED",
    "INTERESTED",
    "VISIT_TRIAL_SCHEDULED",
    "VISIT_COMPLETED",
    "NEGOTIATION",
    "DEAL",
    "REGISTRATION_FORM_PURCHASED",
    "PAYMENT_PENDING",
    "PAYMENT_VERIFIED",
    "UNIFORM_MEASUREMENT",
    "UNIFORM_READY",
    "ENROLLED",
    "LOST",
]

LEAD_STATUS_LABELS = {
    "NEW_LEAD": "New",
    "CONTACTED": "Contacted",
    "INTERESTED": "Interested",
    "VISIT_TRIAL_SCHEDULED": "Visit / Trial",
    "VISIT_COMPLETED": "Visit Done",
    "NEGOTIATION": "Negotiation",
    "DEAL": "Deal",
    "REGISTRATION_FORM_PURCHASED": "Form Paid",
    "PAYMENT_PENDING": "Payment Pending",
    "PAYMENT_VERIFIED": "Payment Verified",
    "UNIFORM_MEASUREMENT": "Uniform",
    "UNIFORM_READY": "Uniform Ready",
    "ENROLLED": "Converted",
    "LOST": "Lost",
}

FINANCE_VISIBLE_STATUSES = [
    "DEAL",
    "REGISTRATION_FORM_PURCHASED",
    "PAYMENT_PENDING",
    "PAYMENT_VERIFIED",
    "UNIFORM_MEASUREMENT",
    "UNIFORM_READY",
    "ENROLLED",
]

PAYMENT_CATEGORIES = [
    "REGISTRATION_FORM",
    "ENROLMENT_FEE",
    "DEVELOPMENT_FEE",
    "UNIFORM_FEE",
]

PAYMENT_CATEGORY_LABELS = {
    "REGISTRATION_FORM": "Registration Form",
    "ENROLMENT_FEE": "Enrolment Fee",
    "DEVELOPMENT_FEE": "Development Fee",
    "UNIFORM_FEE": "Uniform Fee",
}

SPECIAL_CONDITION_TYPES = [
    "FINANCIAL_DIFFICULTY",
    "INSTALLMENT_REQUEST",
    "TEMPORARY_PAYMENT_DELAY",
    "SCHOLARSHIP_CONSIDERATION",
    "DISCOUNT_REQUEST",
    "FAMILY_CONDITION",
    "OTHER",
]

SPECIAL_CONDITION_STATUSES = [
    "ACTIVE",
    "MONITORING",
    "RESOLVED",
    "CANCELLED",
]

ROLE_PAGES = {
    "ADMIN_PPDB": [
        "Input Lead",
        "All Leads",
        "Update Follow Up",
        "Special Condition",
        "Payment History",
        "Per Student",
    ],
    "FINANCE": [
        "Eligible Leads",
        "Add Billing Item",
        "Add Payment",
        "Payment History",
        "Per Student",
        "Special Conditions",
    ],
    "PRINCIPAL": [
        "Leads",
        "Payments",
        "Per Student",
        "Special Conditions",
        "Audit Logs",
        "Lead Source",
    ],
}

ROLE_LABELS = {
    "ADMIN_PPDB": "Admin PPDB",
    "FINANCE": "Finance",
    "PRINCIPAL": "Principal",
    "MARKETER": "Marketer",
}

PAGE_ICONS = {
    "Input Lead": "👥",
    "All Leads": "👥",
    "Update Follow Up": "📅",
    "Special Condition": "☆",
    "Special Conditions": "☆",
    "Payment History": "💳",
    "Per Student": "🎓",
    "Eligible Leads": "👥",
    "Add Billing Item": "🧾",
    "Add Payment": "💳",
    "Leads": "👥",
    "Payments": "💳",
    "Audit Logs": "📋",
    "Lead Source": "📊",
}


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Data and formatting helpers

def get_secret(name: str) -> str:
    try:
        value = st.secrets[name]
        if value:
            return value
    except Exception:
        pass

    return os.getenv(name, "")


def get_attr(obj, name, default=None):
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(name, default)

    return getattr(obj, name, default)


def get_logo_path():
    here = Path(__file__).resolve().parent
    possible_paths = [
        Path("logo_tbcis.png"),
        Path("assets/logo_tbcis.png"),
        Path("images/logo_tbcis.png"),
        here / "logo_tbcis.png",
        here / "assets" / "logo_tbcis.png",
        here / "images" / "logo_tbcis.png",
    ]

    for path in possible_paths:
        if path.exists():
            return str(path)

    return None


@st.cache_data(show_spinner=False)
def get_logo_base64():
    # ini buat nempelin logo langsung ke markdown HTML, soalnya
    # st.markdown ga bisa rujuk file lokal pakai <img src="path">,
    # mesti di-encode dulu jadi data-uri
    logo_path = get_logo_path()
    if not logo_path:
        return None

    try:
        raw = Path(logo_path).read_bytes()
        return base64.b64encode(raw).decode("utf-8")
    except Exception:
        return None


def format_rupiah(value, with_prefix=True):
    if value is None or value == "":
        value = 0

    number = float(value)
    formatted = f"{number:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    if with_prefix:
        return f"Rp {formatted}"

    return formatted


def parse_rupiah(value):
    if value is None:
        return 0.0

    text = str(value).strip()

    if text == "":
        return 0.0

    text = text.replace("Rp", "")
    text = text.replace("rp", "")
    text = text.replace(" ", "")
    text = text.replace(".", "")
    text = text.replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return 0.0


def normalize_phone(value):
    if value is None:
        return ""

    text = str(value).strip()
    text = text.replace(" ", "")
    text = text.replace("-", "")
    text = text.replace("(", "")
    text = text.replace(")", "")

    if text.startswith("+62"):
        text = "0" + text[3:]
    elif text.startswith("62"):
        text = "0" + text[2:]

    return text


def is_valid_phone(value):
    phone = normalize_phone(value)
    return phone.isdigit() and phone.startswith("0") and 10 <= len(phone) <= 12


def safe_text(value, default="-"):
    if value is None or value == "":
        return default
    return str(value)


def label_status(value):
    if value in LEAD_STATUS_LABELS:
        return LEAD_STATUS_LABELS[value]
    if value is None:
        return "-"
    return str(value).replace("_", " ").title()


def label_category(value):
    if value in PAYMENT_CATEGORY_LABELS:
        return PAYMENT_CATEGORY_LABELS[value]
    if value is None:
        return "-"
    return str(value).replace("_", " ").title()


def status_class(value):
    text = label_status(value).lower()
    if "paid" in text and "partial" not in text:
        return "success"
    if "verified" in text or "enrolled" in text or "converted" in text or "deal" in text or "contacted" in text or "active" in text or "resolved" in text:
        return "success"
    if "partial" in text or "pending" in text or "follow" in text or "trial" in text or "monitor" in text or "review" in text:
        return "warning"
    if "lost" in text or "failed" in text or "cancelled" in text or "overdue" in text:
        return "danger"
    if "new" in text or "interested" in text:
        return "info"
    return "neutral"


def date_only(value):
    if not value:
        return "-"
    return str(value)[:10]


# Supabase helpers

def get_supabase():
    url = get_secret("SUPABASE_URL")
    key = get_secret("SUPABASE_ANON_KEY")

    if not url or not key:
        st.error("Supabase secrets are missing. Add SUPABASE_URL and SUPABASE_ANON_KEY.")
        st.stop()

    client = create_client(url, key)

    access_token = st.session_state.get("access_token")
    refresh_token = st.session_state.get("refresh_token")

    if access_token and refresh_token:
        try:
            client.auth.set_session(access_token, refresh_token)
        except Exception:
            pass

        try:
            client.postgrest.auth(access_token)
        except Exception:
            pass

    return client


def supabase_data(response):
    return getattr(response, "data", None) or []


def load_profile(email: str):
    sb = get_supabase()

    result = (
        sb.table("app_users")
        .select("email, full_name, role, active")
        .eq("email", email.lower())
        .limit(1)
        .execute()
    )

    rows = supabase_data(result)

    if not rows:
        return None

    profile = rows[0]

    if profile.get("active") is not True:
        return None

    return profile


def clear_auth_state():
    for key in ["access_token", "refresh_token", "user_email", "profile", "current_page"]:
        if key in st.session_state:
            del st.session_state[key]


def logout():
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass

    clear_auth_state()
    st.rerun()


def fetch_leads(profile):
    sb = get_supabase()
    query = sb.table("leads").select("*").order("created_at", desc=True)

    if profile["role"] == "MARKETER":
        query = query.eq("assigned_marketer_email", profile["email"])

    if profile["role"] == "FINANCE":
        query = query.in_("status", FINANCE_VISIBLE_STATUSES)

    response = query.execute()
    return supabase_data(response)


def fetch_payment_obligations():
    response = (
        get_supabase()
        .table("payment_obligations")
        .select("*, leads(admission_id, student_name, parent_name, target_level, target_class)")
        .order("created_at", desc=True)
        .execute()
    )
    return supabase_data(response)


def fetch_payments():
    response = (
        get_supabase()
        .table("payments")
        .select(
            "*, "
            "leads(admission_id, student_name, parent_name), "
            "payment_obligations(category, description, amount_due, due_date)"
        )
        .order("created_at", desc=True)
        .execute()
    )
    return supabase_data(response)


def fetch_special_conditions():
    response = (
        get_supabase()
        .table("admission_special_conditions")
        .select("*, leads(admission_id, student_name, parent_name)")
        .order("created_at", desc=True)
        .execute()
    )
    return supabase_data(response)


def fetch_audit_logs():
    response = (
        get_supabase()
        .table("audit_logs")
        .select("*")
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    return supabase_data(response)


def count_status(leads, status):
    return len([item for item in leads if item.get("status") == status])


def total_paid_all(payments):
    return sum(
        float(item.get("amount") or 0)
        for item in payments
        if str(item.get("status", "")).upper() == "PAID"
    )


def obligation_paid_map(payments):
    paid = {}

    for payment in payments:
        if str(payment.get("status", "")).upper() != "PAID":
            continue

        obligation_id = payment.get("obligation_id")

        if not obligation_id:
            continue

        paid[obligation_id] = paid.get(obligation_id, 0) + float(payment.get("amount") or 0)

    return paid


def update_obligation_status(obligation_id):
    if not obligation_id:
        return

    sb = get_supabase()

    obligation_response = (
        sb.table("payment_obligations")
        .select("id, amount_due")
        .eq("id", obligation_id)
        .limit(1)
        .execute()
    )

    obligations = supabase_data(obligation_response)

    if not obligations:
        return

    amount_due = float(obligations[0].get("amount_due") or 0)

    payment_response = (
        sb.table("payments")
        .select("amount, status")
        .eq("obligation_id", obligation_id)
        .eq("status", "PAID")
        .execute()
    )

    paid_amount = sum(
        float(item.get("amount") or 0)
        for item in supabase_data(payment_response)
    )

    if paid_amount >= amount_due:
        new_status = "PAID"
    elif paid_amount > 0:
        new_status = "PARTIAL"
    else:
        new_status = "OPEN"

    sb.table("payment_obligations").update(
        {"status": new_status}
    ).eq("id", obligation_id).execute()


# UI helpers

def inject_css():
    st.markdown(
        """
        <style>
        :root {
            --blue-900: #062a73;
            --blue-800: #063b95;
            --blue-700: #0756c7;
            --blue-600: #0b6de5;
            --blue-100: #eaf3ff;
            --ink: #0b1f56;
            --muted: #6b7894;
            --line: #dfe8f5;
            --surface: #ffffff;
            --bg: #f5faff;
            --green: #0aa86b;
            --orange: #f28c1b;
            --purple: #7c55e7;
            --red: #e95454;
            --teal: #18b9c6;
        }

        html {
            zoom: 1.05;
        }

        html, body, [data-testid="stAppViewContainer"] {
            background: radial-gradient(circle at top left, #f8fcff 0, #f5faff 38%, #eef6ff 100%);
        }

        .block-container {
            padding-top: 1.0rem;
            padding-bottom: 2.5rem;
            max-width: 1600px;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0757c9 0%, #064299 48%, #053075 100%);
        }

        [data-testid="stSidebar"] * {
            color: white;
        }

        [data-testid="stSidebar"] img {
            display: block;
            margin-left: auto;
            margin-right: auto;
            max-height: 120px;
            object-fit: contain;
        }

        [data-testid="stSidebar"] .stButton > button {
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.10);
            color: #ffffff;
            border-radius: 14px;
            min-height: 44px;
            font-weight: 700;
            justify-content: flex-start;
            padding-left: 14px;
        }

        [data-testid="stSidebar"] .stButton > button:hover {
            background: rgba(255,255,255,0.18);
            border-color: rgba(255,255,255,0.35);
        }

        .login-card {
            max-width: 520px;
            margin: 18px auto;
            padding: 26px;
            border: 1px solid var(--line);
            border-radius: 26px;
            background: rgba(255,255,255,0.92);
            box-shadow: 0 18px 50px rgba(8, 50, 120, 0.12);
        }

        .topbar {
            background: rgba(255,255,255,0.94);
            border: 1px solid var(--line);
            border-radius: 22px;
            padding: 14px 18px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 12px 34px rgba(7, 60, 150, 0.06);
            margin-bottom: 18px;
        }

        .brand-left {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .brand-mark {
            font-size: 34px;
            color: var(--ink);
            font-weight: 900;
            font-family: Georgia, 'Times New Roman', serif;
            letter-spacing: -0.8px;
        }

        .brand-logo-img {
            height: 46px;
            width: 46px;
            object-fit: contain;
            border-radius: 50%;
            flex-shrink: 0;
        }

        .brand-divider {
            width: 1px;
            height: 42px;
            background: #acc1df;
        }

        .brand-school {
            color: var(--ink);
            font-weight: 800;
            font-size: 15px;
            line-height: 1.25;
        }

        .brand-system {
            color: var(--blue-700);
            font-weight: 700;
            font-size: 13px;
            margin-top: 2px;
        }

        .profile-box {
            display: flex;
            align-items: center;
            gap: 14px;
            color: var(--ink);
        }

        .bell {
            position: relative;
            font-size: 20px;
            color: var(--ink);
        }

        .badge-dot {
            position: absolute;
            top: -9px;
            right: -9px;
            background: #ff4b4b;
            color: white;
            width: 18px;
            height: 18px;
            border-radius: 99px;
            font-size: 11px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
        }

        .avatar {
            width: 40px;
            height: 40px;
            border-radius: 99px;
            background: linear-gradient(135deg, #0b6de5, #21c0d4);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 900;
        }

        .profile-name {
            color: var(--ink);
            font-weight: 800;
            font-size: 15px;
        }

        .profile-role {
            color: var(--muted);
            font-size: 13px;
            margin-top: -2px;
        }

        .page-head {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 12px;
            margin: 8px 0 18px 0;
        }

        .page-title {
            color: var(--ink);
            font-size: 31px;
            font-weight: 900;
            line-height: 1.15;
            margin: 0;
        }

        .breadcrumb {
            color: var(--blue-700);
            font-size: 14px;
            margin-top: 6px;
            font-weight: 650;
        }

        .date-pill {
            background: white;
            border: 1px solid #bfd0ea;
            border-radius: 12px;
            padding: 12px 16px;
            color: var(--ink);
            font-weight: 750;
            box-shadow: 0 8px 24px rgba(12, 67, 150, 0.05);
            white-space: nowrap;
        }

        .metric-card {
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 15px;
            padding: 14px 14px;
            min-height: 108px;
            box-shadow: 0 12px 28px rgba(11, 65, 140, 0.06);
            display: flex;
            gap: 14px;
            align-items: center;
        }

        .metric-icon {
            width: 50px;
            height: 50px;
            border-radius: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 24px;
            font-weight: 900;
            flex-shrink: 0;
        }

        .metric-icon.blue { background: linear-gradient(135deg, #0b6de5, #2459e6); }
        .metric-icon.teal { background: linear-gradient(135deg, #20c6d4, #0aa7b4); }
        .metric-icon.orange { background: linear-gradient(135deg, #ff9d2e, #e77a13); }
        .metric-icon.purple { background: linear-gradient(135deg, #8e65f3, #653ce0); }
        .metric-icon.green { background: linear-gradient(135deg, #19bc75, #06844f); }
        .metric-icon.red { background: linear-gradient(135deg, #ff6b6b, #d93838); }

        .metric-label {
            color: #3e4d6f;
            font-weight: 750;
            font-size: 13px;
            margin-bottom: 4px;
        }

        .metric-value {
            color: var(--ink);
            font-weight: 900;
            font-size: 27px;
            line-height: 1.1;
        }

        .metric-trend {
            color: #0b9d61;
            font-size: 12px;
            font-weight: 800;
            margin-top: 5px;
        }

        .nav-card {
            background: white;
            border: 1px solid var(--line);
            border-radius: 14px;
            box-shadow: 0 10px 28px rgba(11, 65, 140, 0.06);
            padding: 8px 12px 2px 12px;
            margin: 20px 0 16px 0;
        }

        .nav-card .stButton > button {
            background: transparent;
            border: 0;
            border-radius: 0;
            color: #435170;
            font-weight: 800;
            padding: 10px 4px;
            border-bottom: 3px solid transparent;
        }

        .nav-card .stButton > button:hover {
            color: var(--blue-700);
            background: #f4f8ff;
            border-bottom-color: var(--blue-700);
        }

        .section-card {
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 22px;
            box-shadow: 0 12px 30px rgba(11, 65, 140, 0.06);
            margin-bottom: 16px;
        }

        .section-title {
            color: var(--ink);
            font-size: 21px;
            font-weight: 900;
            margin-bottom: 2px;
        }

        .section-caption {
            color: var(--muted);
            font-size: 14px;
            margin-bottom: 16px;
        }

        .recent-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid #edf2fa;
        }

        .recent-left {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .initial-circle {
            width: 42px;
            height: 42px;
            border-radius: 99px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #e8f2ff;
            color: var(--blue-700);
            font-weight: 900;
        }

        .recent-name {
            color: var(--ink);
            font-weight: 850;
            font-size: 14px;
        }

        .recent-meta {
            color: var(--muted);
            font-size: 12px;
            margin-top: 2px;
        }

        .status-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 5px 10px;
            border-radius: 999px;
            font-weight: 850;
            font-size: 12px;
            white-space: nowrap;
        }

        .status-success { background: #dff7ed; color: #08774d; }
        .status-warning { background: #fff1d7; color: #b45c00; }
        .status-danger { background: #ffe2e2; color: #c52727; }
        .status-info { background: #e5f0ff; color: #0b56c4; }
        .status-neutral { background: #eef2f7; color: #536276; }

        .ams-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            overflow: hidden;
            border: 1px solid #e2ebf7;
            border-radius: 14px;
            font-size: 13px;
        }

        .ams-table thead th {
            background: #f7faff;
            color: #22345f;
            text-align: left;
            padding: 12px 12px;
            font-weight: 900;
            border-bottom: 1px solid #e2ebf7;
        }

        .ams-table tbody td {
            padding: 11px 12px;
            border-bottom: 1px solid #edf2fa;
            color: #24365d;
            vertical-align: middle;
        }

        .ams-table tbody tr:last-child td {
            border-bottom: 0;
        }

        .ams-table tbody tr:hover td {
            background: #f8fbff;
        }

        .table-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            color: var(--muted);
            font-size: 13px;
            margin-top: 14px;
        }

        .page-num {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 30px;
            height: 30px;
            border-radius: 8px;
            border: 1px solid #dce7f5;
            color: #264064;
            margin-left: 4px;
            font-weight: 800;
        }

        .page-num.active {
            background: var(--blue-700);
            color: #fff;
            border-color: var(--blue-700);
        }

        .total-red {
            color: #e02d2d;
            font-weight: 900;
        }

        .total-green {
            color: #078f58;
            font-weight: 900;
        }

        .soft-info {
            background: #eef6ff;
            border: 1px solid #cfe2ff;
            padding: 14px 16px;
            border-radius: 14px;
            color: var(--ink);
            font-weight: 750;
        }

        .mini-tabs {
            display: flex;
            gap: 12px;
            margin-bottom: 14px;
            color: var(--blue-700);
            font-weight: 850;
        }

        div[data-testid="stMetric"] {
            background: white;
            border: 1px solid var(--line);
            padding: 16px;
            border-radius: 14px;
            box-shadow: 0 8px 22px rgba(11, 65, 140, 0.05);
        }

        .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"], .stDateInput input {
            border-radius: 12px;
        }

        .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
            background: linear-gradient(135deg, #0b6de5, #075bd1);
            border: 0;
            border-radius: 12px;
            box-shadow: 0 8px 18px rgba(7, 82, 200, 0.20);
            font-weight: 900;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_topbar(profile):
    role_label = ROLE_LABELS.get(profile.get("role"), profile.get("role", "User"))
    full_name = profile.get("full_name") or profile.get("email") or "User"
    initial = (full_name[:1] or "U").upper()

    logo_b64 = get_logo_base64()
    if logo_b64:
        brand_mark_html = f'<img src="data:image/png;base64,{logo_b64}" class="brand-logo-img" alt="TBCIS" />'
    else:
        brand_mark_html = '<div class="brand-mark">TBCIS</div>'

    st.markdown(
        f"""
        <div class="topbar">
            <div class="brand-left">
                {brand_mark_html}
                <div class="brand-divider"></div>
                <div>
                    <div class="brand-school">{escape(SCHOOL_NAME)}</div>
                    <div class="brand-system">Admission Management System</div>
                </div>
            </div>
            <div class="profile-box">
                <div class="bell">🔔<span class="badge-dot">3</span></div>
                <div class="avatar">{escape(initial)}</div>
                <div>
                    <div class="profile-name">{escape(full_name)}</div>
                    <div class="profile-role">{escape(role_label)}</div>
                </div>
                <div style="color:#51607c;font-weight:900;">⌄</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_page_head(title, subtitle=None):
    if subtitle is None:
        subtitle = title
    st.markdown(
        f"""
        <div class="page-head">
            <div>
                <h1 class="page-title">{escape(title)}</h1>
                <div class="breadcrumb">Home  ›  {escape(subtitle)}</div>
            </div>
            <div class="date-pill">📅 {date.today().strftime('%b %d, %Y')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_cards(cards):
    cols = st.columns(len(cards))
    colors = ["blue", "teal", "orange", "purple", "green", "red"]
    for i, card in enumerate(cards):
        color = card.get("color") or colors[i % len(colors)]
        with cols[i]:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-icon {color}">{escape(card.get('icon', '●'))}</div>
                    <div>
                        <div class="metric-label">{escape(card.get('label', 'Metric'))}</div>
                        <div class="metric-value">{escape(str(card.get('value', '0')))}</div>
                        <div class="metric-trend">↗ {escape(card.get('trend', 'vs last month'))}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def admin_metrics(leads):
    return [
        {"icon": "👥", "label": "Total Leads", "value": len(leads), "trend": "18% vs last month", "color": "blue"},
        {"icon": "👤", "label": "New Leads (This Month)", "value": count_status(leads, "NEW_LEAD"), "trend": "23% vs last month", "color": "teal"},
        {"icon": "📅", "label": "Follow Up Today", "value": count_status(leads, "CONTACTED") + count_status(leads, "INTERESTED"), "trend": "9% vs yesterday", "color": "orange"},
        {"icon": "⌛", "label": "Pending Follow Up", "value": count_status(leads, "PAYMENT_PENDING") + count_status(leads, "NEGOTIATION"), "trend": "15% vs last month", "color": "purple"},
        {"icon": "✓", "label": "Converted (This Month)", "value": count_status(leads, "ENROLLED"), "trend": "25% vs last month", "color": "green"},
    ]


def finance_metrics(leads, obligations, payments):
    total_due = sum(float(item.get("amount_due") or 0) for item in obligations)
    total_paid = total_paid_all(payments)
    paid_map = obligation_paid_map(payments)
    overdue = len([item for item in obligations if float(item.get("amount_due") or 0) - paid_map.get(item.get("id"), 0) > 0])
    return [
        {"icon": "👥", "label": "Eligible Students", "value": len(leads), "trend": "18% vs last month", "color": "blue"},
        {"icon": "🧾", "label": "Pending Bill Items", "value": overdue, "trend": "22% vs last month", "color": "orange"},
        {"icon": "👤", "label": "Est. Amount (IDR)", "value": format_rupiah(total_due, False), "trend": "16% vs last month", "color": "teal"},
        {"icon": "✓", "label": "Total Paid", "value": format_rupiah(total_paid, False), "trend": "24% vs last month", "color": "green"},
    ]


def principal_metrics(leads, payments):
    return [
        {"icon": "👥", "label": "Total Leads", "value": len(leads), "trend": "18% vs last month", "color": "blue"},
        {"icon": "👤", "label": "New Leads (This Month)", "value": count_status(leads, "NEW_LEAD"), "trend": "23% vs last month", "color": "teal"},
        {"icon": "📅", "label": "Follow Up Today", "value": count_status(leads, "CONTACTED") + count_status(leads, "INTERESTED"), "trend": "9% vs yesterday", "color": "orange"},
        {"icon": "✓", "label": "Converted (This Month)", "value": count_status(leads, "ENROLLED"), "trend": "25% vs last month", "color": "green"},
    ]


def render_horizontal_nav(role, pages):
    st.markdown('<div class="nav-card">', unsafe_allow_html=True)
    cols = st.columns(len(pages))
    current = st.session_state.get("current_page", pages[0])

    for idx, page in enumerate(pages):
        icon = PAGE_ICONS.get(page, "•")
        label = f"{icon} {page}"
        with cols[idx]:
            if st.button(label, key=f"topnav_{role}_{page}", use_container_width=True):
                st.session_state["current_page"] = page
                st.rerun()
            if current == page:
                st.markdown(
                    "<div style='height:3px;background:#0b6de5;border-radius:99px;margin-top:-6px;'></div>",
                    unsafe_allow_html=True,
                )
    st.markdown('</div>', unsafe_allow_html=True)


def render_sidebar(profile, pages):
    logo_path = get_logo_path()
    if logo_path:
        col_l, col_c, col_r = st.sidebar.columns([1, 2, 1])
        with col_c:
            st.image(logo_path, use_container_width=True)
    else:
        st.sidebar.markdown("# TBCIS")

    st.sidebar.markdown(
        "<div style='text-align:center;font-weight:900;font-size:18px;margin-top:6px;'>TBCIS</div>",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        "<div style='text-align:center;opacity:.85;font-size:12.5px;margin-top:-4px;'>Admission Management System</div>",
        unsafe_allow_html=True,
    )
    st.sidebar.divider()

    for page in pages:
        icon = PAGE_ICONS.get(page, "•")
        if st.sidebar.button(f"{icon}  {page}", key=f"side_{page}", use_container_width=True):
            st.session_state["current_page"] = page
            st.rerun()

    st.sidebar.divider()
    st.sidebar.write(f"**{profile.get('full_name', 'User')}**")
    st.sidebar.caption(ROLE_LABELS.get(profile.get("role"), profile.get("role", "User")))
    if st.sidebar.button("Logout", use_container_width=True):
        logout()


def badge(value):
    return f"<span class='status-badge status-{status_class(value)}'>{escape(label_status(value))}</span>"


def render_table(rows, columns, badge_columns=None, footer_text=None):
    badge_columns = set(badge_columns or [])
    if not rows:
        st.info("No data available.")
        return

    header = "".join(f"<th>{escape(col)}</th>" for col in columns)
    body_rows = []
    for row in rows:
        cells = []
        for col in columns:
            value = row.get(col, "")
            if col in badge_columns:
                cells.append(f"<td>{badge(value)}</td>")
            else:
                cells.append(f"<td>{escape(str(value))}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")

    html = f"""
    <table class="ams-table">
        <thead><tr>{header}</tr></thead>
        <tbody>{''.join(body_rows)}</tbody>
    </table>
    <div class="table-footer">
        <div>{escape(footer_text or f'Showing 1 to {len(rows)} results')}</div>
        <div><span class="page-num active">1</span><span class="page-num">2</span><span class="page-num">3</span><span class="page-num">›</span></div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def initials(name):
    name = safe_text(name, "U")
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name[:2].upper()


def render_recent_leads(leads):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown(
        "<div style='display:flex;justify-content:space-between;align-items:center;'>"
        "<div><div class='section-title'>👥 Recent Leads</div></div>"
        "<div style='color:#0b6de5;font-weight:900;'>View All →</div></div>",
        unsafe_allow_html=True,
    )

    for lead in leads[:5]:
        name = safe_text(lead.get("student_name"), "Student")
        meta = f"{safe_text(lead.get('target_level'))} • {safe_text(lead.get('target_class'))}"
        status = lead.get("status") or "NEW_LEAD"
        st.markdown(
            f"""
            <div class="recent-item">
                <div class="recent-left">
                    <div class="initial-circle">{escape(initials(name))}</div>
                    <div>
                        <div class="recent-name">{escape(name)}</div>
                        <div class="recent-meta">{escape(meta)}</div>
                    </div>
                </div>
                <div>{badge(status)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        "<div style='margin-top:16px;border:1px solid #dce7f5;border-radius:12px;padding:12px;text-align:center;color:#0b6de5;font-weight:900;'>View All Leads →</div>",
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)


def lead_rows(leads, limit=10):
    rows = []
    for i, lead in enumerate(leads[:limit], start=1):
        lead_label = f"{safe_text(lead.get('student_name'))}\n{safe_text(lead.get('parent_phone'))}"
        rows.append(
            {
                "No.": i,
                "Lead": lead_label,
                "Source": safe_text(lead.get("source")),
                "Target": f"{safe_text(lead.get('target_level'))} • {safe_text(lead.get('target_class'))}",
                "Next Follow Up": date_only(lead.get("next_follow_up_at")),
                "Status": lead.get("status") or "NEW_LEAD",
                "Created Date": date_only(lead.get("created_at")),
                "Action": "⋮",
            }
        )
    return rows


def simple_lead_rows(leads, limit=10):
    rows = []
    for i, lead in enumerate(leads[:limit], start=1):
        rows.append(
            {
                "Admission ID": safe_text(lead.get("admission_id")),
                "Source": safe_text(lead.get("source")),
                "Parent Name": safe_text(lead.get("parent_name")),
                "Parent Phone": safe_text(lead.get("parent_phone")),
                "Student Name": safe_text(lead.get("student_name")),
                "Target Level": safe_text(lead.get("target_level")),
                "Target Class": safe_text(lead.get("target_class")),
                "Status": lead.get("status") or "NEW_LEAD",
                "Next Follow Up": date_only(lead.get("next_follow_up_at")),
                "Notes": safe_text(lead.get("notes")),
            }
        )
    return rows


def payments_rows(payments, limit=10):
    rows = []
    for payment in payments[:limit]:
        lead = payment.get("leads") or {}
        obligation = payment.get("payment_obligations") or {}
        rows.append(
            {
                "Date": date_only(payment.get("payment_date") or payment.get("created_at")),
                "Admission ID": safe_text(lead.get("admission_id")),
                "Student Name": safe_text(lead.get("student_name")),
                "Parent Name": safe_text(lead.get("parent_name")),
                "Category": label_category(obligation.get("category") or payment.get("item")),
                "Amount Paid": format_rupiah(payment.get("amount")),
                "Status": payment.get("status") or "PAID",
                "Receipt": safe_text(payment.get("receipt_number")),
                "Verified By": safe_text(payment.get("verified_by_email")),
            }
        )
    return rows


def conditions_rows(conditions, limit=10):
    rows = []
    for item in conditions[:limit]:
        lead = item.get("leads") or {}
        rows.append(
            {
                "Admission ID": safe_text(lead.get("admission_id")),
                "Student Name": safe_text(lead.get("student_name")),
                "Parent Name": safe_text(lead.get("parent_name")),
                "Payment Category": label_category(item.get("payment_category")),
                "Condition Type": safe_text(item.get("condition_type")).replace("_", " ").title(),
                "Summary": safe_text(item.get("summary")),
                "Payment Plan": safe_text(item.get("payment_plan")),
                "Follow Up Date": date_only(item.get("follow_up_date")),
                "Status": item.get("status") or "ACTIVE",
            }
        )
    return rows


def audit_rows(audit_logs, limit=10):
    rows = []
    for item in audit_logs[:limit]:
        rows.append(
            {
                "Created At": date_only(item.get("created_at")),
                "Actor": safe_text(item.get("actor_email")),
                "Action": safe_text(item.get("action")),
                "Table Name": safe_text(item.get("table_name")),
                "Admission ID": safe_text(item.get("admission_id")),
                "Details": "👁",
            }
        )
    return rows


def filter_by_search(rows, query, fields):
    if not query:
        return rows
    q = query.lower().strip()
    return [
        row for row in rows
        if any(q in str(row.get(field, "")).lower() for field in fields)
    ]


# Forms and page components

def lead_form(profile):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("<div class='section-title'>📝 Input Lead</div><div class='section-caption'>Enter new lead information below</div>", unsafe_allow_html=True)

    with st.form("lead_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            source = st.selectbox("Source *", ["Website", "Social Media", "Education Fair", "Referral", "Walk-in", "Marketer Approach"])
            parent_email = st.text_input("Parent Email", placeholder="parent@email.com")
            target_class = st.text_input("Target Class *", placeholder="Grade 7")
        with col2:
            parent_name = st.text_input("Parent Name *", placeholder="Enter parent name")
            student_name = st.text_input("Student Name *", placeholder="Enter student name")
            academic_year = st.text_input("Academic Year *", value="2026/2027")
        with col3:
            parent_phone = st.text_input("Parent Phone *", placeholder="081234567890")
            target_level = st.selectbox("Target Level *", ["EY", "Primary", "Lower Secondary", "Upper Secondary"])
            next_follow_up_date = st.date_input("Next Follow Up Date *", value=date.today())

        notes = st.text_area("Notes", placeholder="Add any notes about this lead...")
        col_space, col_button = st.columns([4, 1])
        with col_button:
            submitted = st.form_submit_button("✈ Save Lead", type="primary", use_container_width=True)

    if submitted:
        if not parent_name or not parent_phone or not student_name or not target_class:
            st.warning("Parent name, phone, student name, and target class are required.")
            st.markdown('</div>', unsafe_allow_html=True)
            return

        parent_phone = normalize_phone(parent_phone)

        if not is_valid_phone(parent_phone):
            st.warning("Parent phone must start with 0 and contain 10 to 12 digits only.")
            st.markdown('</div>', unsafe_allow_html=True)
            return

        payload = {
            "source": source,
            "parent_name": parent_name,
            "parent_phone": parent_phone,
            "parent_email": parent_email or None,
            "student_name": student_name,
            "target_level": target_level,
            "target_class": target_class,
            "academic_year": academic_year,
            "status": "NEW_LEAD",
            "assigned_marketer_email": None,
            "created_by_email": profile["email"],
            "next_follow_up_at": str(next_follow_up_date) if next_follow_up_date else None,
            "notes": notes or None,
        }

        try:
            get_supabase().table("leads").insert(payload).execute()
            st.success("Lead saved.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not save lead: {exc}")

    st.markdown('</div>', unsafe_allow_html=True)


def update_lead_status_form(leads):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("<div class='section-title'>📅 Update Follow Up</div><div class='section-caption'>Update follow up information and status</div>", unsafe_allow_html=True)

    if not leads:
        st.info("No lead data available.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    options = {
        f"{lead.get('admission_id')} - {lead.get('parent_name')} ({lead.get('student_name')})": lead
        for lead in leads
    }

    with st.form("update_lead_status_form"):
        col1, col2 = st.columns([1, 1])
        with col1:
            selected_label = st.selectbox("Select Lead *", list(options.keys()))
            selected = options[selected_label]
            st.markdown(
                f"""
                <div class="soft-info">
                    <div style="font-weight:900;">{escape(safe_text(selected.get('student_name')))}</div>
                    <div style="font-size:13px;color:#6b7894;">{escape(safe_text(selected.get('target_level')))} • {escape(safe_text(selected.get('target_class')))}</div>
                    <div style="font-size:13px;margin-top:8px;">Source: {escape(safe_text(selected.get('source')))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col2:
            st.write("Current Status")
            st.markdown(badge(selected.get("status")), unsafe_allow_html=True)
            new_status = st.selectbox(
                "Update Status *",
                LEAD_STATUSES,
                format_func=label_status,
                index=LEAD_STATUSES.index(selected.get("status")) if selected.get("status") in LEAD_STATUSES else 0,
            )
            next_follow_up = st.date_input("Next Follow Up Date *", value=date.today())

        notes = st.text_area("Notes *", value=selected.get("notes") or "", placeholder="Add notes about this follow up...")
        col_space, col_button = st.columns([4, 1])
        with col_button:
            submitted = st.form_submit_button("Update Follow Up", type="primary", use_container_width=True)

    if submitted:
        payload = {
            "status": new_status,
            "notes": notes or None,
            "last_follow_up_at": datetime.utcnow().isoformat(),
            "next_follow_up_at": str(next_follow_up) if next_follow_up else None,
        }

        try:
            get_supabase().table("leads").update(payload).eq("id", selected["id"]).execute()
            st.success("Lead status updated.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not update status: {exc}")

    st.markdown('</div>', unsafe_allow_html=True)


def special_condition_form(profile, leads):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("<div class='section-title'>☆ Special Condition</div><div class='section-caption'>Record and manage special condition for applicants.</div>", unsafe_allow_html=True)

    if not leads:
        st.info("No lead data available.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    options = {
        f"{lead.get('admission_id')} - {lead.get('student_name')} ({lead.get('parent_name')})": lead
        for lead in leads
    }

    with st.form("special_condition_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            selected_label = st.selectbox("Select Student *", list(options.keys()))
            selected = options[selected_label]
            condition_type = st.selectbox("Condition Type *", SPECIAL_CONDITION_TYPES, format_func=lambda x: x.replace("_", " ").title())
        with col2:
            payment_category = st.selectbox("Payment Category *", PAYMENT_CATEGORIES, format_func=label_category)
            status = st.selectbox("Status *", SPECIAL_CONDITION_STATUSES, format_func=lambda x: x.title())
        with col3:
            follow_up_date = st.date_input("Follow Up Date *", value=date.today())
            requested_by = st.text_input("Requested By *", value="Admin PPDB")

        summary = st.text_input("Short Summary *", placeholder="Installment request due to family financial planning.")
        detail = st.text_area("Condition Detail *", placeholder="Describe the student's condition in detail...")
        payment_reason = st.text_area("Reason for Installment / Partial Payment *", placeholder="Explain the reason for partial payment or installment...")
        payment_plan = st.text_area("Proposed Payment Plan *", placeholder="Example: 3 installments, Rp 5.000.000,00 each month.")

        col_space, col_button = st.columns([4, 1])
        with col_button:
            submitted = st.form_submit_button("✈ Save Special Condition", type="primary", use_container_width=True)

    if submitted:
        if not summary:
            st.warning("Short summary is required.")
            st.markdown('</div>', unsafe_allow_html=True)
            return

        payload = {
            "lead_id": selected["id"],
            "payment_category": payment_category,
            "condition_type": condition_type,
            "summary": summary,
            "detail": detail or None,
            "payment_reason": payment_reason or None,
            "payment_plan": payment_plan or None,
            "requested_by": requested_by or None,
            "follow_up_date": str(follow_up_date) if follow_up_date else None,
            "status": status,
            "created_by_email": profile["email"],
        }

        try:
            get_supabase().table("admission_special_conditions").insert(payload).execute()
            st.success("Special condition saved. Finance can now see it.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not save special condition: {exc}")

    st.markdown('</div>', unsafe_allow_html=True)


def billing_item_form(profile, leads):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("<div class='section-title'>🧾 Add Billing Item</div><div class='section-caption'>Create a new billing item for a student.</div>", unsafe_allow_html=True)

    if not leads:
        st.info("No eligible leads. Change lead status to Deal or Payment Pending first.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    options = {
        f"{lead.get('admission_id')} - {lead.get('student_name')} ({lead.get('parent_name')})": lead
        for lead in leads
    }

    with st.form("billing_item_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            selected_label = st.selectbox("Student *", list(options.keys()))
            selected = options[selected_label]
            description = st.text_area("Description *", placeholder="Enter billing item description...")
            amount_due_text = st.text_input("Amount Due (IDR) *", value="0,00", placeholder="Contoh: 1.000.000,00")
        with col2:
            category = st.selectbox("Billing Category *", PAYMENT_CATEGORIES, format_func=label_category)
            due_date = st.date_input("Due Date *", value=date.today())
            notes = st.text_area("Notes", placeholder="Add any additional notes...")

        amount_due = parse_rupiah(amount_due_text)
        st.caption(f"Amount detected: {format_rupiah(amount_due)}")

        col_space, col_button = st.columns([4, 1])
        with col_button:
            submitted = st.form_submit_button("✈ Save Billing Item", type="primary", use_container_width=True)

    if submitted:
        if amount_due <= 0:
            st.warning("Amount due must be greater than 0. Use format like 1.000.000,00.")
            st.markdown('</div>', unsafe_allow_html=True)
            return

        payload = {
            "lead_id": selected["id"],
            "category": category,
            "description": description or label_category(category),
            "amount_due": amount_due,
            "due_date": str(due_date) if due_date else None,
            "status": "OPEN",
            "created_by_email": profile["email"],
        }

        try:
            get_supabase().table("payment_obligations").insert(payload).execute()
            st.success("Billing item saved.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not save billing item: {exc}")

    st.markdown('</div>', unsafe_allow_html=True)


def payment_form(profile, obligations, payments):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("<div class='section-title'>💳 Add Payment</div><div class='section-caption'>Record a payment against a billing item.</div>", unsafe_allow_html=True)

    if not obligations:
        st.info("No billing items yet. Create a billing item first.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    paid_map = obligation_paid_map(payments)
    selectable = []

    for item in obligations:
        amount_due = float(item.get("amount_due") or 0)
        paid = paid_map.get(item["id"], 0)
        balance = amount_due - paid

        if balance > 0:
            lead = item.get("leads") or {}
            label = (
                f"{lead.get('admission_id')} - {lead.get('student_name')} - "
                f"{item.get('description')} - Balance {format_rupiah(balance)}"
            )
            selectable.append((label, item, balance))

    if not selectable:
        st.success("All billing items are fully paid.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    with st.form("payment_form", clear_on_submit=True):
        selected_label = st.selectbox("Billing Item *", [item[0] for item in selectable])
        selected_tuple = next(item for item in selectable if item[0] == selected_label)
        selected_obligation = selected_tuple[1]
        balance = selected_tuple[2]

        st.markdown(
            f"""
            <div class="soft-info" style="display:flex;justify-content:space-between;">
                <div><div style="color:#6b7894;font-size:12px;">Maximum Payable</div><div>{escape(format_rupiah(balance))}</div></div>
                <div><div style="color:#6b7894;font-size:12px;">Outstanding Balance</div><div>{escape(format_rupiah(balance))}</div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns(2)
        with col1:
            amount_text = st.text_input("Amount Paid (IDR) *", value="0,00", placeholder="Contoh: 1.000.000,00")
            receipt_number = st.text_input("Receipt Number *", placeholder="RCPT-0001")
        with col2:
            payment_method = st.selectbox("Payment Method *", ["Bank Transfer", "Cash", "Virtual Account", "Other"])
            payment_date = st.date_input("Payment Date *", value=date.today())

        notes = st.text_area("Notes", placeholder="Add any notes about this payment...")
        amount = parse_rupiah(amount_text)
        st.caption(f"Amount detected: {format_rupiah(amount)}")

        col_space, col_button = st.columns([4, 1])
        with col_button:
            submitted = st.form_submit_button("✈ Save Payment", type="primary", use_container_width=True)

    if submitted:
        if amount <= 0:
            st.warning("Amount must be greater than 0. Use format like 50.000,00.")
            st.markdown('</div>', unsafe_allow_html=True)
            return

        if amount > balance:
            st.warning(f"Amount paid cannot be more than the balance: {format_rupiah(balance)}")
            st.markdown('</div>', unsafe_allow_html=True)
            return

        payload = {
            "lead_id": selected_obligation["lead_id"],
            "obligation_id": selected_obligation["id"],
            "item": selected_obligation["category"],
            "amount": amount,
            "status": "PAID",
            "receipt_number": receipt_number or None,
            "payment_date": str(payment_date),
            "verified_by_email": profile["email"],
            "notes": notes or None,
        }

        try:
            get_supabase().table("payments").insert(payload).execute()
            update_obligation_status(selected_obligation["id"])
            st.success("Payment saved.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not save payment: {exc}")

    st.markdown('</div>', unsafe_allow_html=True)


def student_payment_summary(leads, obligations, payments):
    paid_map = obligation_paid_map(payments)
    rows = []

    for lead in leads:
        lead_obligations = [item for item in obligations if item.get("lead_id") == lead.get("id")]
        amount_due = sum(float(item.get("amount_due") or 0) for item in lead_obligations)
        paid = sum(paid_map.get(item.get("id"), 0) for item in lead_obligations)
        balance = amount_due - paid
        rows.append(
            {
                "Admission ID": safe_text(lead.get("admission_id")),
                "Student Name": safe_text(lead.get("student_name")),
                "Parent Name": safe_text(lead.get("parent_name")),
                "Total Due": format_rupiah(amount_due),
                "Total Paid": format_rupiah(paid),
                "Balance": format_rupiah(balance),
                "Status": "PAID" if amount_due > 0 and balance <= 0 else ("PARTIAL" if paid > 0 else "UNPAID"),
                "raw_balance": balance,
            }
        )
    return rows


def get_special_condition_text(lead, conditions, payment_category=None):
    lead_conditions = [item for item in conditions if item.get("lead_id") == lead.get("id")]

    if payment_category:
        lead_conditions = [item for item in lead_conditions if item.get("payment_category") == payment_category]

    if not lead_conditions:
        return "-"

    texts = []
    for condition in lead_conditions:
        summary = safe_text(condition.get("summary"), "")
        plan = safe_text(condition.get("payment_plan"), "")
        parts = [part for part in [summary, plan] if part]
        texts.append(" | ".join(parts))
    return " || ".join(texts) if texts else "-"


def per_student_view(leads, obligations, payments, conditions):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("<div class='section-title'>🎓 Per Student</div><div class='section-caption'>View financial summary and payment details per student.</div>", unsafe_allow_html=True)

    search = st.text_input("Search by student name or Admission ID", key="per_student_search")
    filtered_leads = leads
    if search:
        q = search.lower()
        filtered_leads = [
            lead for lead in leads
            if q in safe_text(lead.get("student_name")).lower() or q in safe_text(lead.get("admission_id")).lower()
        ]

    summary = student_payment_summary(filtered_leads, obligations, payments)
    display_summary = [{k: v for k, v in row.items() if k != "raw_balance"} for row in summary[:10]]
    render_table(
        display_summary,
        ["Admission ID", "Student Name", "Parent Name", "Total Due", "Total Paid", "Balance", "Status"],
        badge_columns=["Status"],
        footer_text=f"Showing 1 to {min(len(display_summary), 10)} of {len(summary)} students",
    )

    if filtered_leads:
        options = {f"{lead.get('admission_id')} - {lead.get('student_name')}": lead for lead in filtered_leads}
        selected_label = st.selectbox("Select student to see payment breakdown", list(options.keys()))
        selected_lead = options[selected_label]
        paid_map = obligation_paid_map(payments)
        lead_obligations = [item for item in obligations if item.get("lead_id") == selected_lead.get("id")]
        detail_rows = []
        for item in lead_obligations:
            item_due = float(item.get("amount_due") or 0)
            item_paid = paid_map.get(item.get("id"), 0)
            balance = item_due - item_paid
            status = "PAID" if balance <= 0 else ("PARTIAL" if item_paid > 0 else "UNPAID")
            detail_rows.append(
                {
                    "Category": label_category(item.get("category")),
                    "Description": safe_text(item.get("description")),
                    "Due Date": date_only(item.get("due_date")),
                    "Amount": format_rupiah(item_due),
                    "Paid": format_rupiah(item_paid),
                    "Balance": format_rupiah(balance),
                    "Status": status,
                    "Special Condition": get_special_condition_text(selected_lead, conditions, item.get("category")),
                }
            )

        st.markdown("<br><div class='section-title' style='font-size:18px;'>Payment Breakdown</div>", unsafe_allow_html=True)
        render_table(
            detail_rows,
            ["Category", "Description", "Due Date", "Amount", "Paid", "Balance", "Status", "Special Condition"],
            badge_columns=["Status"],
            footer_text=f"Showing {len(detail_rows)} billing items",
        )

        payment_history = [payment for payment in payments if payment.get("lead_id") == selected_lead.get("id")]
        if payment_history:
            st.markdown("<br><div class='section-title' style='font-size:18px;'>Payment History</div>", unsafe_allow_html=True)
            render_table(
                payments_rows(payment_history, 10),
                ["Date", "Admission ID", "Student Name", "Parent Name", "Category", "Amount Paid", "Status", "Receipt", "Verified By"],
                badge_columns=["Status"],
                footer_text=f"Showing {min(10, len(payment_history))} payments",
            )

    st.markdown('</div>', unsafe_allow_html=True)


# Page views

def admin_input_lead_page(profile, leads):
    col1, col2 = st.columns([2, 1])
    with col1:
        lead_form(profile)
    with col2:
        render_recent_leads(leads)


def admin_all_leads_page(leads):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("<div class='section-title'>All Leads</div><div class='section-caption'>Manage and view all leads</div>", unsafe_allow_html=True)
    search = st.text_input("Search by name, email, or phone", key="all_leads_search")
    rows = simple_lead_rows(leads, 500)
    rows = filter_by_search(rows, search, ["Admission ID", "Parent Name", "Parent Phone", "Student Name"])
    render_table(
        rows[:10],
        ["Admission ID", "Source", "Parent Name", "Parent Phone", "Student Name", "Target Level", "Target Class", "Status", "Next Follow Up", "Notes"],
        badge_columns=["Status"],
        footer_text=f"Showing 1 to {min(len(rows), 10)} of {len(rows)} results",
    )
    st.markdown('</div>', unsafe_allow_html=True)


def payment_history_page(payments, title="Payment History"):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown(f"<div class='section-title'>💳 {escape(title)}</div><div class='section-caption'>View and track all payment transactions.</div>", unsafe_allow_html=True)
    search = st.text_input("Search by Admission ID, student or parent name", key=f"payment_search_{title}")
    rows = payments_rows(payments, 500)
    rows = filter_by_search(rows, search, ["Admission ID", "Student Name", "Parent Name", "Receipt"])
    render_table(
        rows[:10],
        ["Date", "Admission ID", "Student Name", "Parent Name", "Category", "Amount Paid", "Status", "Receipt", "Verified By"],
        badge_columns=["Status"],
        footer_text=f"Showing 1 to {min(len(rows), 10)} of {len(rows)} payments",
    )
    st.markdown('</div>', unsafe_allow_html=True)


def finance_eligible_leads_page(leads):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("<div class='section-title'>Eligible Leads</div><div class='section-caption'>View students who are ready for billing.</div>", unsafe_allow_html=True)
    search = st.text_input("Search by name, student ID, or parent name", key="eligible_search")
    rows = []
    for i, lead in enumerate(leads[:500], start=1):
        rows.append(
            {
                "No.": i,
                "Admission ID": safe_text(lead.get("admission_id")),
                "Parent": safe_text(lead.get("parent_name")),
                "Student": safe_text(lead.get("student_name")),
                "Target": f"{safe_text(lead.get('target_level'))} • {safe_text(lead.get('target_class'))}",
                "Status": lead.get("status") or "DEAL",
                "Notes": safe_text(lead.get("notes")),
            }
        )
    rows = filter_by_search(rows, search, ["Admission ID", "Parent", "Student"])
    render_table(
        rows[:10],
        ["No.", "Admission ID", "Parent", "Student", "Target", "Status", "Notes"],
        badge_columns=["Status"],
        footer_text=f"Showing 1 to {min(len(rows), 10)} of {len(rows)} leads",
    )
    st.markdown('</div>', unsafe_allow_html=True)


def special_conditions_page(conditions):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("<div class='section-title'>☆ Special Conditions</div><div class='section-caption'>Search and view special payment conditions.</div>", unsafe_allow_html=True)
    search = st.text_input("Search by student name, condition, or description", key="conditions_search")
    rows = conditions_rows(conditions, 500)
    rows = filter_by_search(rows, search, ["Admission ID", "Student Name", "Parent Name", "Summary", "Payment Plan"])
    render_table(
        rows[:10],
        ["Admission ID", "Student Name", "Parent Name", "Payment Category", "Condition Type", "Summary", "Payment Plan", "Follow Up Date", "Status"],
        badge_columns=["Status"],
        footer_text=f"Showing 1 to {min(len(rows), 10)} of {len(rows)} conditions",
    )
    st.markdown('</div>', unsafe_allow_html=True)


def audit_logs_page(audit_logs):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("<div class='section-title'>📋 Audit Logs</div><div class='section-caption'>View system activities and audit trail.</div>", unsafe_allow_html=True)
    render_table(
        audit_rows(audit_logs, 10),
        ["Created At", "Actor", "Action", "Table Name", "Admission ID", "Details"],
        badge_columns=["Action"],
        footer_text=f"Showing 1 to {min(len(audit_logs), 10)} of {len(audit_logs)} logs",
    )
    st.markdown('</div>', unsafe_allow_html=True)


def lead_source_page(leads):
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("<div class='section-title'>📊 Lead Source</div><div class='section-caption'>Analyse where your leads are coming from.</div>", unsafe_allow_html=True)

    if not leads:
        st.info("No leads yet.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    df = pd.DataFrame(leads)
    if "source" not in df.columns:
        st.info("Source data is not available.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    source_counts = df["source"].fillna("Unknown").value_counts().reset_index()
    source_counts.columns = ["Source", "Total Leads"]
    st.bar_chart(source_counts.set_index("Source"))

    rows = []
    for _, row in source_counts.iterrows():
        source = row["Source"]
        total = int(row["Total Leads"])
        converted = len([lead for lead in leads if lead.get("source") == source and lead.get("status") == "ENROLLED"])
        rate = f"{(converted / total * 100):.1f}%" if total else "0%"
        rows.append({"Source": source, "Total Leads": total, "Converted Leads": converted, "Conversion Rate": rate})

    render_table(rows, ["Source", "Total Leads", "Converted Leads", "Conversion Rate"], footer_text=f"Showing 1 to {len(rows)} sources")
    st.markdown('</div>', unsafe_allow_html=True)


# Dashboards

def dashboard_shell(profile, leads, obligations=None, payments=None):
    obligations = obligations or []
    payments = payments or []
    role = profile.get("role")
    role_label = ROLE_LABELS.get(role, role)
    render_topbar(profile)
    render_page_head(role_label, role_label)

    if role == "ADMIN_PPDB":
        metric_cards(admin_metrics(leads))
    elif role == "FINANCE":
        metric_cards(finance_metrics(leads, obligations, payments))
    else:
        metric_cards(principal_metrics(leads, payments))

    render_horizontal_nav(role, ROLE_PAGES[role])


def admin_dashboard(profile):
    leads = fetch_leads(profile)
    obligations = fetch_payment_obligations()
    payments = fetch_payments()
    conditions = fetch_special_conditions()

    visible_lead_ids = {lead.get("id") for lead in leads}
    visible_obligations = [item for item in obligations if item.get("lead_id") in visible_lead_ids]
    visible_payments = [item for item in payments if item.get("lead_id") in visible_lead_ids]
    visible_conditions = [item for item in conditions if item.get("lead_id") in visible_lead_ids]

    dashboard_shell(profile, leads, visible_obligations, visible_payments)
    page = st.session_state.get("current_page", "Input Lead")

    if page == "Input Lead":
        admin_input_lead_page(profile, leads)
    elif page == "All Leads":
        admin_all_leads_page(leads)
    elif page == "Update Follow Up":
        col1, col2 = st.columns([2, 1])
        with col1:
            update_lead_status_form(leads)
        with col2:
            render_recent_leads(leads)
    elif page == "Special Condition":
        special_condition_form(profile, leads)
    elif page == "Payment History":
        payment_history_page(visible_payments)
    elif page == "Per Student":
        per_student_view(leads, visible_obligations, visible_payments, visible_conditions)


def finance_dashboard(profile):
    leads = fetch_leads(profile)
    obligations = fetch_payment_obligations()
    payments = fetch_payments()
    conditions = fetch_special_conditions()

    visible_lead_ids = {lead.get("id") for lead in leads}
    visible_obligations = [item for item in obligations if item.get("lead_id") in visible_lead_ids]
    visible_payments = [item for item in payments if item.get("lead_id") in visible_lead_ids]
    visible_conditions = [item for item in conditions if item.get("lead_id") in visible_lead_ids]

    dashboard_shell(profile, leads, visible_obligations, visible_payments)
    page = st.session_state.get("current_page", "Eligible Leads")

    if page == "Eligible Leads":
        finance_eligible_leads_page(leads)
    elif page == "Add Billing Item":
        billing_item_form(profile, leads)
    elif page == "Add Payment":
        payment_form(profile, visible_obligations, visible_payments)
    elif page == "Payment History":
        payment_history_page(visible_payments)
    elif page == "Per Student":
        per_student_view(leads, visible_obligations, visible_payments, visible_conditions)
    elif page == "Special Conditions":
        special_conditions_page(visible_conditions)


def principal_dashboard(profile):
    leads = fetch_leads(profile)
    obligations = fetch_payment_obligations()
    payments = fetch_payments()
    conditions = fetch_special_conditions()
    audit_logs = fetch_audit_logs()

    dashboard_shell(profile, leads, obligations, payments)
    page = st.session_state.get("current_page", "Leads")

    if page == "Leads":
        admin_all_leads_page(leads)
    elif page == "Payments":
        payment_history_page(payments, title="Payments")
    elif page == "Per Student":
        per_student_view(leads, obligations, payments, conditions)
    elif page == "Special Conditions":
        special_conditions_page(conditions)
    elif page == "Audit Logs":
        audit_logs_page(audit_logs)
    elif page == "Lead Source":
        lead_source_page(leads)


# Authentication and app entry

def login_page():
    logo_path = get_logo_path()
    st.markdown("<br>", unsafe_allow_html=True)
    if logo_path:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            st.image(logo_path, use_container_width=True)

    st.markdown(
        f"""
        <div style="text-align:center;margin-top:8px;margin-bottom:18px;">
            <div style="font-size:38px;font-weight:900;color:#0b1f56;font-family:Georgia,'Times New Roman',serif;">TBCIS</div>
            <div style="font-size:24px;font-weight:900;color:#0b1f56;">{escape(APP_TITLE)}</div>
            <div style="color:#6b7894;font-weight:650;margin-top:4px;">{escape(SCHOOL_NAME)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.subheader("Staff Login")
        st.caption("Use the email and password created by the school admin.")
        email = st.text_input("Email", placeholder="staff@tbcis.sch.id")
        password = st.text_input("Password", type="password", placeholder="Password")
        col1, col2 = st.columns([1, 1])
        with col1:
            login_clicked = st.button("Login", use_container_width=True, type="primary")
        with col2:
            forgot_clicked = st.button("Forgot password", use_container_width=True)

        if login_clicked:
            if not email or not password:
                st.warning("Fill in email and password.")
                return

            sb = get_supabase()
            try:
                auth_response = sb.auth.sign_in_with_password({"email": email.strip().lower(), "password": password})
            except Exception as exc:
                st.error(f"Login failed: {exc}")
                return

            session = get_attr(auth_response, "session")
            user = get_attr(auth_response, "user")
            if not session or not user:
                st.error("Login failed. Check your email and password.")
                return

            st.session_state["access_token"] = get_attr(session, "access_token")
            st.session_state["refresh_token"] = get_attr(session, "refresh_token")
            user_email = get_attr(user, "email", email.strip().lower())
            st.session_state["user_email"] = user_email.lower()
            profile = load_profile(user_email)

            if not profile:
                clear_auth_state()
                st.error("Access denied. This email is not active in app_users.")
                return

            st.session_state["profile"] = profile
            role = profile.get("role")
            if role in ROLE_PAGES:
                st.session_state["current_page"] = ROLE_PAGES[role][0]
            st.rerun()

        if forgot_clicked:
            if not email:
                st.warning("Type your email first.")
                return
            try:
                get_supabase().auth.reset_password_for_email(email.strip().lower())
                st.success("Password reset email sent.")
            except Exception as exc:
                st.error(f"Could not send reset email: {exc}")


def main_app():
    inject_css()
    profile = st.session_state.get("profile")
    if not profile:
        login_page()
        return

    role = profile.get("role")
    if role == "MARKETER":
        st.error("The MARKETER role is no longer used. Please login with an ADMIN_PPDB account.")
        return

    if role not in ROLE_PAGES:
        st.error("Unknown role. Contact system administrator.")
        return

    pages = ROLE_PAGES[role]
    if st.session_state.get("current_page") not in pages:
        st.session_state["current_page"] = pages[0]

    render_sidebar(profile, pages)

    if role == "ADMIN_PPDB":
        admin_dashboard(profile)
    elif role == "FINANCE":
        finance_dashboard(profile)
    elif role == "PRINCIPAL":
        principal_dashboard(profile)


main_app()
