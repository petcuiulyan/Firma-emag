"""Utilitare comune pentru pagini: incarcare date, configurare coloane, export."""
import io
from contextlib import contextmanager

import pandas as pd
import streamlit as st

import core_costing as costing
import core_schema as schema
import core_storage as storage

PCT_COLS = {"duty_pct", "vat_pct", "vat_pct", "commission_pct", "returns_pct"}


def load_all():
    """Incarca tabelele si setarile de pe disc."""
    return {n: storage.load(n) for n in schema.SPECS}, storage.load_settings()


def compute_all():
    d, s = load_all()
    oc, lc = costing.compute(d["orders"], d["lines"], s)
    return d, s, oc, lc


def column_config(name, hide=()):
    sel = {"goods_cur": schema.CURRENCIES, "transp_cur": schema.CURRENCIES, "currency": schema.CURRENCIES,
           "transport_type": schema.TRANSPORT_TYPES, "transp_basis": schema.BASES, "volumetric": ["Da", "Nu"],
           "alloc_method": schema.METHODS, "status": schema.STATUSES}
    cfg = {}
    for col, kind, _, label in schema.SPECS[name]:
        if col in hide:
            cfg[col] = None
        elif col in sel:
            cfg[col] = st.column_config.SelectboxColumn(label, options=sel[col])
        elif kind == "date":
            cfg[col] = st.column_config.DateColumn(label, format="DD.MM.YYYY")
        elif kind == "num":
            cfg[col] = st.column_config.NumberColumn(label, format="percent" if col in PCT_COLS else "%.4g")
        else:
            cfg[col] = st.column_config.TextColumn(label)
    return cfg


def to_xlsx(sheets: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name[:31], index=False)
    return buf.getvalue()


def money(x, cur="RON"):
    return "–" if x != x or x is None else f"{x:,.2f} {cur}"


def info_empty(msg="Nu există date încă."):
    st.info(msg)


@contextmanager
def guard():
    """Prinde modificarile in luni inchise: afiseaza eroare si opreste scriptul (nu se salveaza nimic)."""
    try:
        yield
    except storage.PeriodClosedError as e:
        st.error(f"🔒 Lună închisă – {e}")
        st.stop()


def api_key():
    try:
        k = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        k = ""
    return k or st.session_state.get("ai_key", "")


def ai_model():
    import core_ai as ai
    try:
        return st.secrets.get("ANTHROPIC_MODEL", "") or st.session_state.get("ai_model", ai.DEFAULT_MODEL)
    except Exception:
        return st.session_state.get("ai_model", ai.DEFAULT_MODEL)
