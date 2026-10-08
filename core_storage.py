"""Persistenta: CSV/JSON in folderul data/ + backup/restore in Excel + import din calculatorul .xlsx vechi."""
import io
import json
import os
from pathlib import Path

import pandas as pd

import core_schema as schema
from core_settings import DEFAULTS, merged

DATA_DIR = Path(os.environ.get("IMPORT_APP_DATA", Path(__file__).resolve().parent / "data"))


def _path(name): return DATA_DIR / f"{name}.csv"


def load(name):
    p = _path(name)
    df = pd.read_csv(p, dtype=str, keep_default_na=False, na_values=[""]) if p.exists() else pd.DataFrame()
    return schema.coerce(name, df)


def save(name, df):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = schema.coerce(name, df)
    for c, k, _, _ in schema.SPECS[name]:
        if k == "date":
            out[c] = out[c].dt.strftime("%Y-%m-%d")
    out.to_csv(_path(name), index=False)


def load_settings():
    p = DATA_DIR / "settings.json"
    return merged(json.loads(p.read_text(encoding="utf-8")) if p.exists() else {})


def save_settings(s):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "settings.json").write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- backup / restore
def export_backup():
    """Toate tabelele + setarile intr-un singur .xlsx (descarcabil)."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name in schema.SPECS:
            load(name).to_excel(xw, sheet_name=name, index=False)
        pd.DataFrame({"json": [json.dumps(load_settings(), ensure_ascii=False)]}).to_excel(xw, sheet_name="settings", index=False)
    return buf.getvalue()


def restore_backup(file):
    xl = pd.ExcelFile(file)
    for name in schema.SPECS:
        if name in xl.sheet_names:
            save(name, xl.parse(name, dtype=str))
    if "settings" in xl.sheet_names:
        save_settings(merged(json.loads(xl.parse("settings").iloc[0, 0])))


# ---------------------------------------------------------------- import din calculatorul Excel
_ORDER_MAP = "id date supplier pi_no incoterm transport_type goods_cur usd_ron eur_ron transp_cur transp_basis transp_rate " \
             "min_chargeable volumetric insurance n_categories flat_fee_eur n_parcels logistics_lei local_ron duty_pct vat_pct alloc_method".split()
_LINE_MAP = "order_id sku description qty unit_price unit_weight_kg pcs_per_carton carton_l carton_w carton_h cbm_per_pc ro_price notes".split()


def import_legacy_excel(file):
    """Citeste 'Comenzi' (rand 9+, A:W) si 'PI Furnizor' (rand 7+, A:M) din Calculator_Cost_Import_Mostre.xlsx."""
    xl = pd.ExcelFile(file)
    o = xl.parse("Comenzi", header=None, skiprows=8, usecols="A:W", names=_ORDER_MAP)
    o = o[o["id"].notna() & (o["id"].astype(str).str.strip() != "")].copy()
    o["status"] = "Receptionata"
    l = xl.parse("PI Furnizor", header=None, skiprows=6, usecols="A:M", names=_LINE_MAP)
    l = l[l["order_id"].notna() & (l["qty"].notna())].copy()
    o["id"] = o["id"].astype(str).str.strip(); l["order_id"] = l["order_id"].astype(str).str.strip()
    l["sku"] = l["sku"].astype(str).str.strip()
    # in calculatorul vechi procentele se pot lasa goale -> raman NaN (se foloseste valoarea implicita)
    return schema.coerce("orders", o), schema.coerce("lines", l)
