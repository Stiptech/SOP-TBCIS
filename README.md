# TBCIS Admission Management System, Streamlit Version

Dashboard PPDB sederhana untuk Terang Bangsa Cambridge International School.

## Isi aplikasi

- Login email dan password memakai Supabase Auth
- Role access dari tabel app_users
- Dashboard Marketer
- Dashboard Admin PPDB
- Dashboard Finance
- Dashboard Principal
- Input lead
- Update status lead
- Input payment
- Payment history
- Audit log untuk Principal
- Lead source chart

## File penting

- app.py
- requirements.txt
- .streamlit/secrets.toml.example

## Cara jalan di laptop

1. Install Python 3.10 atau lebih baru.
2. Buka folder ini di VS Code.
3. Install library:

```bash
pip install -r requirements.txt
```

4. Buat file:

```text
.streamlit/secrets.toml
```

5. Isi:

```toml
SUPABASE_URL = "https://your-project-id.supabase.co"
SUPABASE_ANON_KEY = "your_supabase_anon_key"
```

6. Jalankan:

```bash
streamlit run app.py
```

## Catatan deploy

Streamlit Community Cloud biasanya deploy dari GitHub repository. Kalau tidak mau GitHub, app ini tetap bisa jalan lokal di laptop, atau dipasang di server sendiri.

Jangan masukkan service_role key ke Streamlit.
Gunakan anon key saja.
Database security tetap dikunci lewat Supabase RLS.
