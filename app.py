import os
from datetime import datetime, date

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

FINANCE_VISIBLE_STATUSES = [
    "DEAL",
    "REGISTRATION_FORM_PURCHASED",
    "PAYMENT_PENDING",
    "PAYMENT_VERIFIED",
    "UNIFORM_MEASUREMENT",
    "UNIFORM_READY",
    "ENROLLED",
]

PAYMENT_ITEMS = [
    "REGISTRATION_FORM",
    "REGISTRATION_FEE",
    "DEVELOPMENT_FEE",
    "UNIFORM_FEE",
]


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🎓",
    layout="wide",
)


def get_secret(name: str) -> str:
    """Read secret from Streamlit secrets first, then environment variable."""
    try:
        value = st.secrets[name]
        if value:
            return value
    except Exception:
        pass
    return os.getenv(name, "")


def get_attr(obj, name, default=None):
    """Supabase objects can behave like objects or dicts depending on version."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def get_supabase():
    """Create Supabase client and attach logged-in user's JWT when available."""
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


def login_page():
    st.markdown(
        f"""
        <div class="login-header">
            <div class="logo-box">TBCIS</div>
            <h1>{APP_TITLE}</h1>
            <p>{SCHOOL_NAME}</p>
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
                auth_response = sb.auth.sign_in_with_password(
                    {
                        "email": email.strip().lower(),
                        "password": password,
                    }
                )
            except Exception as exc:
                st.error(f"Login failed: {exc}")
                return

            session = get_attr(auth_response, "session")
            user = get_attr(auth_response, "user")

            if not session or not user:
                st.error("Login failed. Check your email and password.")
                return

            access_token = get_attr(session, "access_token")
            refresh_token = get_attr(session, "refresh_token")
            user_email = get_attr(user, "email", email.strip().lower())

            st.session_state["access_token"] = access_token
            st.session_state["refresh_token"] = refresh_token
            st.session_state["user_email"] = user_email.lower()

            profile = load_profile(user_email)
            if not profile:
                clear_auth_state()
                st.error("Access denied. This email is not active in app_users.")
                return

            st.session_state["profile"] = profile
            st.rerun()

        if forgot_clicked:
            if not email:
                st.warning("Type your email first.")
                return

            sb = get_supabase()
            try:
                sb.auth.reset_password_for_email(email.strip().lower())
                st.success("Password reset email sent.")
            except Exception as exc:
                st.error(f"Could not send reset email: {exc}")


def clear_auth_state():
    for key in ["access_token", "refresh_token", "user_email", "profile"]:
        if key in st.session_state:
            del st.session_state[key]


def logout():
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    clear_auth_state()
    st.rerun()


def app_sidebar(profile):
    st.sidebar.markdown("## TBCIS")
    st.sidebar.caption("Admission Management")
    st.sidebar.divider()

    st.sidebar.write(f"**{profile['full_name']}**")
    st.sidebar.caption(profile["role"])

    st.sidebar.divider()
    st.sidebar.write("Navigation")
    st.sidebar.info("Dashboard access follows your assigned role.")

    st.sidebar.divider()
    if st.sidebar.button("Logout", use_container_width=True):
        logout()


def fetch_leads(profile):
    sb = get_supabase()
    query = sb.table("leads").select("*").order("created_at", desc=True)

    if profile["role"] == "MARKETER":
        query = query.eq("assigned_marketer_email", profile["email"])

    if profile["role"] == "FINANCE":
        query = query.in_("status", FINANCE_VISIBLE_STATUSES)

    response = query.execute()
    return supabase_data(response)


def fetch_payments():
    sb = get_supabase()
    response = (
        sb.table("payments")
        .select("*, leads(admission_id, student_name, parent_name)")
        .order("created_at", desc=True)
        .execute()
    )
    return supabase_data(response)


def fetch_audit_logs():
    sb = get_supabase()
    response = (
        sb.table("audit_logs")
        .select("*")
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    return supabase_data(response)


def show_stats(leads, payments=None):
    payments = payments or []

    total_paid = sum(
        float(item.get("amount") or 0)
        for item in payments
        if item.get("status") == "PAID"
    )

    enrolled = count_status(leads, "ENROLLED")
    conversion = f"{round((enrolled / len(leads)) * 100)}%" if leads else "0%"

    cols = st.columns(6)
    cols[0].metric("Total Leads", len(leads))
    cols[1].metric("Interested", count_status(leads, "INTERESTED"))
    cols[2].metric("Visit/Trial", count_status(leads, "VISIT_TRIAL_SCHEDULED"))
    cols[3].metric("Deal", count_status(leads, "DEAL"))
    cols[4].metric("Enrolled", enrolled)
    cols[5].metric("Conversion", conversion)

    if payments:
        st.metric("Total Paid", f"Rp {total_paid:,.0f}".replace(",", "."))


def count_status(leads, status):
    return len([item for item in leads if item.get("status") == status])


def leads_dataframe(leads):
    if not leads:
        return pd.DataFrame()

    df = pd.DataFrame(leads)

    columns = [
        "admission_id",
        "source",
        "parent_name",
        "parent_phone",
        "student_name",
        "target_level",
        "target_class",
        "status",
        "next_follow_up_at",
        "assigned_marketer_email",
        "notes",
    ]

    existing = [col for col in columns if col in df.columns]
    return df[existing]


def lead_form(profile):
    st.subheader("Add New Lead")

    with st.form("lead_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            source = st.selectbox(
                "Source",
                ["Website", "Social Media", "Education Fair", "Referral", "Walk-in", "Marketer Approach"],
            )
            parent_name = st.text_input("Parent Name")
            parent_phone = st.text_input("Parent Phone")
            parent_email = st.text_input("Parent Email")

        with col2:
            student_name = st.text_input("Student Name")
            target_level = st.selectbox("Target Level", ["EY", "Primary", "Lower Secondary", "Upper Secondary"])
            target_class = st.text_input("Target Class")
            academic_year = st.text_input("Academic Year", value="2026/2027")

        next_follow_up_date = st.date_input("Next Follow Up Date", value=None)
        notes = st.text_area("Notes")

        submitted = st.form_submit_button("Save Lead", type="primary")

    if submitted:
        if not parent_name or not parent_phone or not student_name or not target_class:
            st.warning("Parent name, phone, student name, and target class are required.")
            return

        assigned_marketer_email = profile["email"] if profile["role"] == "MARKETER" else None

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
            "assigned_marketer_email": assigned_marketer_email,
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


def update_lead_status(leads):
    st.subheader("Update Lead Status")

    if not leads:
        st.info("No lead data available.")
        return

    options = {
        f"{lead['admission_id']} · {lead['student_name']} · {lead['parent_name']}": lead
        for lead in leads
    }

    selected_label = st.selectbox("Select Lead", list(options.keys()))
    selected = options[selected_label]

    with st.form("update_lead_status_form"):
        new_status = st.selectbox(
            "Status",
            LEAD_STATUSES,
            index=LEAD_STATUSES.index(selected["status"]) if selected.get("status") in LEAD_STATUSES else 0,
        )
        next_follow_up = st.date_input("Next Follow Up Date", value=None)
        notes = st.text_area("Follow Up Notes", value=selected.get("notes") or "")

        submitted = st.form_submit_button("Update Status", type="primary")

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


def payment_form(profile, leads):
    st.subheader("Add Payment")

    if not leads:
        st.info("No eligible leads for payment.")
        return

    options = {
        f"{lead['admission_id']} · {lead['student_name']} · {lead['parent_name']}": lead
        for lead in leads
    }

    with st.form("payment_form", clear_on_submit=True):
        selected_label = st.selectbox("Select Lead", list(options.keys()))
        selected = options[selected_label]

        item = st.selectbox("Payment Item", PAYMENT_ITEMS)
        amount = st.number_input("Amount", min_value=0.0, step=100000.0)
        receipt_number = st.text_input("Receipt Number")
        payment_date = st.date_input("Payment Date", value=date.today())
        notes = st.text_area("Notes")

        submitted = st.form_submit_button("Save Payment", type="primary")

    if submitted:
        if amount <= 0:
            st.warning("Amount must be greater than 0.")
            return

        payload = {
            "lead_id": selected["id"],
            "item": item,
            "amount": amount,
            "status": "PAID",
            "receipt_number": receipt_number or None,
            "payment_date": str(payment_date),
            "verified_by_email": profile["email"],
            "notes": notes or None,
        }

        try:
            get_supabase().table("payments").insert(payload).execute()
            st.success("Payment saved. Duplicate paid payment for the same item will be blocked by database.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not save payment: {exc}")


def payments_dataframe(payments):
    if not payments:
        return pd.DataFrame()

    rows = []
    for payment in payments:
        lead = payment.get("leads") or {}
        rows.append(
            {
                "payment_date": payment.get("payment_date"),
                "admission_id": lead.get("admission_id"),
                "student_name": lead.get("student_name"),
                "parent_name": lead.get("parent_name"),
                "item": payment.get("item"),
                "amount": payment.get("amount"),
                "status": payment.get("status"),
                "receipt_number": payment.get("receipt_number"),
                "verified_by_email": payment.get("verified_by_email"),
            }
        )

    return pd.DataFrame(rows)

def payment_summary_per_student(payments):
    if not payments:
        return pd.DataFrame()

    rows = []

    for payment in payments:
        lead = payment.get("leads") or {}

        rows.append(
            {
                "admission_id": lead.get("admission_id"),
                "student_name": lead.get("student_name"),
                "parent_name": lead.get("parent_name"),
                "amount": float(payment.get("amount") or 0),
                "status": payment.get("status"),
            }
        )

    df = pd.DataFrame(rows)

    df = df[df["status"] == "PAID"]

    if df.empty:
        return pd.DataFrame()

    summary = (
        df.groupby(["admission_id", "student_name", "parent_name"], as_index=False)
        ["amount"]
        .sum()
        .rename(columns={"amount": "total_paid"})
    )

    summary["total_paid"] = summary["total_paid"].apply(
        lambda x: f"Rp {x:,.0f}".replace(",", ".")
    )

    return summary

def marketer_dashboard(profile):
    st.title("Marketer Dashboard")
    leads = fetch_leads(profile)

    show_stats(leads)

    tab1, tab2 = st.tabs(["Input Lead", "My Leads"])

    with tab1:
        lead_form(profile)

    with tab2:
        df = leads_dataframe(leads)
        st.dataframe(df, use_container_width=True, hide_index=True)


def admin_dashboard(profile):
    st.title("Admin PPDB Dashboard")
    leads = fetch_leads(profile)

    show_stats(leads)

    tab1, tab2 = st.tabs(["All Leads", "Update Follow Up"])

    with tab1:
        st.dataframe(leads_dataframe(leads), use_container_width=True, hide_index=True)

    with tab2:
        update_lead_status(leads)


def finance_dashboard(profile):
    st.title("Finance Dashboard")
    leads = fetch_leads(profile)
    payments = fetch_payments()

    show_stats(leads, payments)

    tab1, tab2, tab3 = st.tabs(["Eligible Leads", "Add Payment", "Payment History"])

    with tab1:
        st.dataframe(leads_dataframe(leads), use_container_width=True, hide_index=True)

    with tab2:
        payment_form(profile, leads)

    with tab3:
        st.dataframe(payments_dataframe(payments), use_container_width=True, hide_index=True)


def principal_dashboard(profile):
    st.title("Principal Dashboard")
    leads = fetch_leads(profile)
    payments = fetch_payments()
    audit_logs = fetch_audit_logs()

    show_stats(leads, payments)

    tab1, tab2, tab3, tab4 = st.tabs(["Leads", "Payments", "Audit Logs", "Lead Source"])

    with tab1:
        st.dataframe(leads_dataframe(leads), use_container_width=True, hide_index=True)

    with tab2:
        st.dataframe(payments_dataframe(payments), use_container_width=True, hide_index=True)

    with tab3:
        if audit_logs:
            audit_df = pd.DataFrame(audit_logs)
            columns = ["created_at", "actor_email", "action", "table_name", "admission_id"]
            st.dataframe(audit_df[[col for col in columns if col in audit_df.columns]], use_container_width=True, hide_index=True)
        else:
            st.info("No audit logs yet.")

    with tab4:
        if leads:
            df = pd.DataFrame(leads)
            source_counts = df["source"].value_counts().reset_index()
            source_counts.columns = ["Source", "Total"]
            st.bar_chart(source_counts.set_index("Source"))
        else:
            st.info("No leads yet.")


def main_app():
    profile = st.session_state.get("profile")

    if not profile:
        login_page()
        return

    app_sidebar(profile)

    st.markdown(
        f"""
        <div class="school-header">
            <h3>{SCHOOL_NAME}</h3>
            <p>Admission data must be entered only through this system.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    role = profile["role"]

    if role == "MARKETER":
        marketer_dashboard(profile)
    elif role == "ADMIN_PPDB":
        admin_dashboard(profile)
    elif role == "FINANCE":
        finance_dashboard(profile)
    elif role == "PRINCIPAL":
        principal_dashboard(profile)
    else:
        st.error("Unknown role. Contact system administrator.")


st.markdown(
    """
    <style>
    .login-header {
        text-align: center;
        max-width: 760px;
        margin: 40px auto 20px auto;
    }

    .login-header h1 {
        margin-bottom: 8px;
    }

    .login-header p {
        color: #64748b;
    }

    .logo-box {
        display: inline-block;
        background: #183b82;
        color: white;
        padding: 12px 18px;
        border-radius: 14px;
        font-weight: 800;
        letter-spacing: 1px;
        margin-bottom: 12px;
    }

    .school-header {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 16px 20px;
        margin-bottom: 22px;
    }

    .school-header h3 {
        margin: 0 0 4px 0;
    }

    .school-header p {
        margin: 0;
        color: #64748b;
    }

    div[data-testid="stMetric"] {
        background: white;
        border: 1px solid #e5e7eb;
        padding: 16px;
        border-radius: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

main_app()
