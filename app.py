import os
from datetime import datetime, date
from pathlib import Path

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


PAYMENT_CATEGORIES = [
    "REGISTRATION_FORM",
    "ENROLMENT_FEE",
    "DEVELOPMENT_FEE",
    "UNIFORM_FEE",
]


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


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🎓",
    layout="wide",
)


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
    possible_paths = [
        Path("logo_tbcis.png"),
        Path("assets/logo_tbcis.png"),
        Path("images/logo_tbcis.png"),
    ]

    for path in possible_paths:
        if path.exists():
            return str(path)

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


def login_page():
    logo_path = get_logo_path()

    st.markdown('<div class="login-wrapper">', unsafe_allow_html=True)

    if logo_path:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image(logo_path, width=220)

    st.markdown(
        f"""
        <div class="login-header">
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

    st.markdown('</div>', unsafe_allow_html=True)

def app_sidebar(profile):
    logo_path = get_logo_path()

    if logo_path:
        st.sidebar.image(logo_path, use_container_width=True)
    else:
        st.sidebar.markdown("## TBCIS")

    st.sidebar.markdown("### TBCIS")
    st.sidebar.caption("Admission Management System")
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


def fetch_payment_obligations():
    response = (
        get_supabase()
        .table("payment_obligations")
        .select("*, leads(admission_id, student_name, parent_name)")
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
        .limit(50)
        .execute()
    )

    return supabase_data(response)


def count_status(leads, status):
    return len([item for item in leads if item.get("status") == status])


def total_paid_all(payments):
    return sum(
        float(item.get("amount") or 0)
        for item in payments
        if item.get("status") == "PAID"
    )


def show_stats(leads, payments=None):
    payments = payments or []

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
        st.metric("Total Paid, All Students", format_rupiah(total_paid_all(payments)))


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
                [
                    "Website",
                    "Social Media",
                    "Education Fair",
                    "Referral",
                    "Walk-in",
                    "Marketer Approach",
                ],
            )
            parent_name = st.text_input("Parent Name")
            parent_phone = st.text_input("Parent Phone")
            parent_email = st.text_input("Parent Email")

        with col2:
            student_name = st.text_input("Student Name")
            target_level = st.selectbox(
                "Target Level",
                ["EY", "Primary", "Lower Secondary", "Upper Secondary"],
            )
            target_class = st.text_input("Target Class")
            academic_year = st.text_input("Academic Year", value="2026/2027")

        next_follow_up_date = st.date_input("Next Follow Up Date", value=None)
        notes = st.text_area("Notes")

        submitted = st.form_submit_button("Save Lead", type="primary")

    if submitted:
        if not parent_name or not parent_phone or not student_name or not target_class:
            st.warning("Parent name, phone, student name, and target class are required.")
            return

        parent_phone = normalize_phone(parent_phone)

        if not is_valid_phone(parent_phone):
            st.warning("Parent phone must start with 0 and contain 10 to 12 digits only.")
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
            index=LEAD_STATUSES.index(selected["status"])
            if selected.get("status") in LEAD_STATUSES
            else 0,
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


def special_condition_form(profile, leads):
    st.subheader("Add Special Condition")

    if not leads:
        st.info("No lead data available.")
        return

    options = {
        f"{lead['admission_id']} · {lead['student_name']} · {lead['parent_name']}": lead
        for lead in leads
    }

    with st.form("special_condition_form", clear_on_submit=True):
        selected_label = st.selectbox("Select Student", list(options.keys()))
        selected = options[selected_label]

        col1, col2 = st.columns(2)

        with col1:
            payment_category = st.selectbox(
                "Payment Category with Problem",
                PAYMENT_CATEGORIES,
            )
            condition_type = st.selectbox("Condition Type", SPECIAL_CONDITION_TYPES)
            status = st.selectbox("Status", SPECIAL_CONDITION_STATUSES)

        with col2:
            follow_up_date = st.date_input("Finance Follow Up Date", value=None)
            summary = st.text_input(
                "Short Summary",
                placeholder="Example: Parent requests installment for development fee",
            )
            requested_by = st.text_input(
                "Requested By",
                placeholder="Example: Father / Mother",
            )

        detail = st.text_area(
            "Condition Detail",
            placeholder="Explain the parent's situation clearly and objectively.",
        )

        payment_reason = st.text_area(
            "Reason for Partial Payment or Installment",
            placeholder="Example: Parent can pay Rp 500.000,00 first due to temporary cash flow issue.",
        )

        payment_plan = st.text_area(
            "Proposed Payment Plan",
            placeholder="Example: Rp 500.000,00 today, remaining balance paid in 3 installments.",
        )

        submitted = st.form_submit_button("Save Special Condition", type="primary")

    if submitted:
        if not summary:
            st.warning("Short summary is required.")
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


def special_conditions_dataframe(conditions):
    if not conditions:
        return pd.DataFrame()

    rows = []

    for condition in conditions:
        lead = condition.get("leads") or {}

        rows.append(
            {
                "created_at": condition.get("created_at"),
                "admission_id": lead.get("admission_id"),
                "student_name": lead.get("student_name"),
                "parent_name": lead.get("parent_name"),
                "payment_category": condition.get("payment_category"),
                "condition_type": condition.get("condition_type"),
                "summary": condition.get("summary"),
                "payment_reason": condition.get("payment_reason"),
                "payment_plan": condition.get("payment_plan"),
                "follow_up_date": condition.get("follow_up_date"),
                "status": condition.get("status"),
                "created_by_email": condition.get("created_by_email"),
            }
        )

    return pd.DataFrame(rows)


def get_special_condition_text(lead, conditions, payment_category=None):
    lead_conditions = [
        item for item in conditions
        if item.get("lead_id") == lead.get("id")
    ]

    if payment_category:
        lead_conditions = [
            item for item in lead_conditions
            if item.get("payment_category") == payment_category
        ]

    if not lead_conditions:
        return "-"

    texts = []

    for condition in lead_conditions:
        parts = []

        if condition.get("payment_category"):
            parts.append(condition.get("payment_category"))

        if condition.get("condition_type"):
            parts.append(condition.get("condition_type"))

        if condition.get("summary"):
            parts.append(condition.get("summary"))

        if condition.get("payment_reason"):
            parts.append(f"Reason: {condition.get('payment_reason')}")

        if condition.get("payment_plan"):
            parts.append(f"Plan: {condition.get('payment_plan')}")

        if condition.get("follow_up_date"):
            parts.append(f"Follow up: {condition.get('follow_up_date')}")

        if condition.get("status"):
            parts.append(f"Status: {condition.get('status')}")

        texts.append(" | ".join(parts))

    return " || ".join(texts)


def billing_item_form(profile, leads):
    st.subheader("Add Billing Item")

    if not leads:
        st.info("No eligible leads. Change lead status to DEAL or PAYMENT_PENDING first.")
        return

    options = {
        f"{lead['admission_id']} · {lead['student_name']} · {lead['parent_name']}": lead
        for lead in leads
    }

    with st.form("billing_item_form", clear_on_submit=True):
        selected_label = st.selectbox("Select Student", list(options.keys()))
        selected = options[selected_label]

        col1, col2 = st.columns(2)

        with col1:
            category = st.selectbox("Billing Category", PAYMENT_CATEGORIES)
            description = st.text_input("Description", placeholder="Example: Development Fee")

        with col2:
            amount_due_text = st.text_input(
                "Amount Due",
                value="0,00",
                placeholder="Contoh: 1.000.000,00",
            )
            due_date = st.date_input("Due Date", value=None)

        amount_due = parse_rupiah(amount_due_text)
        st.caption(f"Amount detected: {format_rupiah(amount_due)}")

        submitted = st.form_submit_button("Save Billing Item", type="primary")

    if submitted:
        if amount_due <= 0:
            st.warning("Amount due must be greater than 0. Use format like 1.000.000,00.")
            return

        payload = {
            "lead_id": selected["id"],
            "category": category,
            "description": description or category,
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


def obligation_paid_map(payments):
    paid = {}

    for payment in payments:
        if payment.get("status") != "PAID":
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


def payment_form(profile, obligations, payments):
    st.subheader("Add Payment")

    if not obligations:
        st.info("No billing items yet. Create a billing item first.")
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
                f"{lead.get('admission_id')} · "
                f"{lead.get('student_name')} · "
                f"{item.get('description')} · "
                f"Balance {format_rupiah(balance)}"
            )

            selectable.append((label, item, balance))

    if not selectable:
        st.success("All billing items are fully paid.")
        return

    with st.form("payment_form", clear_on_submit=True):
        selected_label = st.selectbox(
            "Select Billing Item",
            [item[0] for item in selectable],
        )

        selected_tuple = next(
            item for item in selectable
            if item[0] == selected_label
        )

        selected_obligation = selected_tuple[1]
        balance = selected_tuple[2]

        st.caption(f"Maximum payment: {format_rupiah(balance)}")

        amount_text = st.text_input(
            "Amount Paid",
            value="0,00",
            placeholder="Contoh: 50.000,00",
        )

        amount = parse_rupiah(amount_text)
        st.caption(f"Amount detected: {format_rupiah(amount)}")

        receipt_number = st.text_input("Receipt Number")
        payment_date = st.date_input("Payment Date", value=date.today())
        notes = st.text_area("Notes")

        submitted = st.form_submit_button("Save Payment", type="primary")

    if submitted:
        if amount <= 0:
            st.warning("Amount must be greater than 0. Use format like 50.000,00.")
            return

        if amount > balance:
            st.warning(f"Amount paid cannot be more than the balance: {format_rupiah(balance)}")
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


def payments_dataframe(payments):
    if not payments:
        return pd.DataFrame()

    rows = []

    for payment in payments:
        lead = payment.get("leads") or {}
        obligation = payment.get("payment_obligations") or {}

        rows.append(
            {
                "payment_date": payment.get("payment_date"),
                "admission_id": lead.get("admission_id"),
                "student_name": lead.get("student_name"),
                "parent_name": lead.get("parent_name"),
                "category": obligation.get("category") or payment.get("item"),
                "description": obligation.get("description"),
                "amount_paid": format_rupiah(payment.get("amount")),
                "status": payment.get("status"),
                "receipt_number": payment.get("receipt_number"),
                "verified_by_email": payment.get("verified_by_email"),
            }
        )

    return pd.DataFrame(rows)


def student_payment_summary(leads, obligations, payments):
    paid_map = obligation_paid_map(payments)

    rows = []

    for lead in leads:
        lead_obligations = [
            item for item in obligations
            if item.get("lead_id") == lead.get("id")
        ]

        amount_due = sum(
            float(item.get("amount_due") or 0)
            for item in lead_obligations
        )

        paid = sum(
            paid_map.get(item.get("id"), 0)
            for item in lead_obligations
        )

        balance = amount_due - paid

        rows.append(
            {
                "admission_id": lead.get("admission_id"),
                "student_name": lead.get("student_name"),
                "parent_name": lead.get("parent_name"),
                "total_due": amount_due,
                "total_paid": paid,
                "balance": balance,
                "payment_status": "PAID"
                if amount_due > 0 and balance <= 0
                else ("PARTIAL" if paid > 0 else "UNPAID"),
            }
        )

    return pd.DataFrame(rows)


def student_payment_expanders(leads, obligations, payments, conditions=None):
    if not leads:
        st.info("No student data available.")
        return

    conditions = conditions or []
    paid_map = obligation_paid_map(payments)

    summary_df = student_payment_summary(leads, obligations, payments)
    display_summary = summary_df.copy()

    for col in ["total_due", "total_paid", "balance"]:
        display_summary[col] = display_summary[col].apply(format_rupiah)

    st.subheader("Student Payment Summary")
    st.dataframe(display_summary, use_container_width=True, hide_index=True)

    st.subheader("Student Payment Details")

    for lead in leads:
        lead_obligations = [
            item for item in obligations
            if item.get("lead_id") == lead.get("id")
        ]

        amount_due = sum(
            float(item.get("amount_due") or 0)
            for item in lead_obligations
        )

        paid = sum(
            paid_map.get(item.get("id"), 0)
            for item in lead_obligations
        )

        title = (
            f"{lead.get('admission_id')} · "
            f"{lead.get('student_name')} · "
            f"{lead.get('parent_name')} · "
            f"Paid {format_rupiah(paid)} / Due {format_rupiah(amount_due)}"
        )

        with st.expander(title):
            if not lead_obligations:
                st.warning("No billing items have been created for this student.")
                continue

            detail_rows = []

            for item in lead_obligations:
                item_paid = paid_map.get(item.get("id"), 0)
                item_due = float(item.get("amount_due") or 0)
                item_balance = item_due - item_paid

                special_condition_text = get_special_condition_text(
                    lead,
                    conditions,
                    item.get("category"),
                )

                detail_rows.append(
                    {
                        "category": item.get("category"),
                        "description": item.get("description"),
                        "amount_due": item_due,
                        "amount_paid": item_paid,
                        "balance": item_balance,
                        "status": "PAID"
                        if item_balance <= 0
                        else ("PARTIAL" if item_paid > 0 else "UNPAID"),
                        "due_date": item.get("due_date"),
                        "special_condition": special_condition_text,
                    }
                )

            detail_df = pd.DataFrame(detail_rows)

            for col in ["amount_due", "amount_paid", "balance"]:
                detail_df[col] = detail_df[col].apply(format_rupiah)

            st.dataframe(detail_df, use_container_width=True, hide_index=True)

            history_rows = []

            for payment in payments:
                if payment.get("lead_id") != lead.get("id"):
                    continue

                obligation = payment.get("payment_obligations") or {}

                history_rows.append(
                    {
                        "payment_date": payment.get("payment_date"),
                        "category": obligation.get("category") or payment.get("item"),
                        "description": obligation.get("description"),
                        "amount_paid": payment.get("amount"),
                        "receipt_number": payment.get("receipt_number"),
                    }
                )

            st.caption("Payment History")

            if history_rows:
                history_df = pd.DataFrame(history_rows)
                history_df["amount_paid"] = history_df["amount_paid"].apply(format_rupiah)
                st.dataframe(history_df, use_container_width=True, hide_index=True)
            else:
                st.info("No payment history yet.")


def marketer_dashboard(profile):
    st.title("Marketer Dashboard")

    leads = fetch_leads(profile)

    show_stats(leads)

    tab1, tab2 = st.tabs(["Input Lead", "My Leads"])

    with tab1:
        lead_form(profile)

    with tab2:
        st.dataframe(
            leads_dataframe(leads),
            use_container_width=True,
            hide_index=True,
        )


def admin_dashboard(profile):
    st.title("Admin PPDB Dashboard")

    leads = fetch_leads(profile)
    obligations = fetch_payment_obligations()
    payments = fetch_payments()
    conditions = fetch_special_conditions()

    visible_lead_ids = {lead.get("id") for lead in leads}

    visible_obligations = [
        item for item in obligations
        if item.get("lead_id") in visible_lead_ids
    ]

    visible_payments = [
        item for item in payments
        if item.get("lead_id") in visible_lead_ids
    ]

    visible_conditions = [
        item for item in conditions
        if item.get("lead_id") in visible_lead_ids
    ]

    show_stats(leads)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "Input Lead",
            "All Leads",
            "Update Follow Up",
            "Special Condition",
            "Payment History",
            "Per Student",
        ]
    )

    with tab1:
        lead_form(profile)

    with tab2:
        st.dataframe(
            leads_dataframe(leads),
            use_container_width=True,
            hide_index=True,
        )

    with tab3:
        update_lead_status(leads)

    with tab4:
        special_condition_form(profile, leads)
        st.divider()
        st.subheader("Recorded Special Conditions")
        st.dataframe(
            special_conditions_dataframe(visible_conditions),
            use_container_width=True,
            hide_index=True,
        )

    with tab5:
        st.subheader("Payment History")
        st.dataframe(
            payments_dataframe(visible_payments),
            use_container_width=True,
            hide_index=True,
        )

    with tab6:
        student_payment_expanders(
            leads,
            visible_obligations,
            visible_payments,
            visible_conditions,
        )

def finance_dashboard(profile):
    st.title("Finance Dashboard")

    leads = fetch_leads(profile)
    obligations = fetch_payment_obligations()
    payments = fetch_payments()
    conditions = fetch_special_conditions()

    visible_lead_ids = {lead.get("id") for lead in leads}

    visible_conditions = [
        item for item in conditions
        if item.get("lead_id") in visible_lead_ids
    ]

    show_stats(leads, payments)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "Eligible Leads",
            "Add Billing Item",
            "Add Payment",
            "Payment History",
            "Per Student",
            "Special Conditions",
        ]
    )

    with tab1:
        st.dataframe(
            leads_dataframe(leads),
            use_container_width=True,
            hide_index=True,
        )

    with tab2:
        billing_item_form(profile, leads)

    with tab3:
        payment_form(profile, obligations, payments)

    with tab4:
        st.dataframe(
            payments_dataframe(payments),
            use_container_width=True,
            hide_index=True,
        )

    with tab5:
        student_payment_expanders(
            leads,
            obligations,
            payments,
            visible_conditions,
        )

    with tab6:
        st.subheader("Special Conditions from Admin PPDB")
        st.dataframe(
            special_conditions_dataframe(visible_conditions),
            use_container_width=True,
            hide_index=True,
        )


def principal_dashboard(profile):
    st.title("Principal Dashboard")

    leads = fetch_leads(profile)
    payments = fetch_payments()
    obligations = fetch_payment_obligations()
    conditions = fetch_special_conditions()
    audit_logs = fetch_audit_logs()

    show_stats(leads, payments)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "Leads",
            "Payments",
            "Per Student",
            "Special Conditions",
            "Audit Logs",
            "Lead Source",
        ]
    )

    with tab1:
        st.dataframe(
            leads_dataframe(leads),
            use_container_width=True,
            hide_index=True,
        )

    with tab2:
        st.dataframe(
            payments_dataframe(payments),
            use_container_width=True,
            hide_index=True,
        )

    with tab3:
        student_payment_expanders(
            leads,
            obligations,
            payments,
            conditions,
        )

    with tab4:
        st.dataframe(
            special_conditions_dataframe(conditions),
            use_container_width=True,
            hide_index=True,
        )

    with tab5:
        if audit_logs:
            audit_df = pd.DataFrame(audit_logs)
            columns = [
                "created_at",
                "actor_email",
                "action",
                "table_name",
                "admission_id",
            ]
            existing = [col for col in columns if col in audit_df.columns]

            st.dataframe(
                audit_df[existing],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No audit logs yet.")

    with tab6:
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

    logo_path = get_logo_path()

    header_col1, header_col2 = st.columns([1, 6])

    with header_col1:
        if logo_path:
            st.image(logo_path, width=92)

    with header_col2:
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
        st.error("The MARKETER role is no longer used. Please login with an ADMIN_PPDB account.")
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


    .login-wrapper {
        max-width: 760px;
        margin: 0 auto;
    }

    .login-header {
        text-align: center;
        max-width: 760px;
        margin: 12px auto 20px auto;
    }

    .login-header h1 {
        margin-bottom: 8px;
        color: #0f2457;
    }

    .login-header p {
        color: #64748b;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #071f4d 0%, #0a3678 100%);
    }

    [data-testid="stSidebar"] * {
        color: white;
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
