"""Structura tabelelor (coloane, tipuri, valori implicite). O singura sursa de adevar:
din ea se genereaza tabele goale, coercitia tipurilor si etichetele din interfata."""
import numpy as np
import pandas as pd

# (coloana, tip, implicit, eticheta)
ORDERS = [
    ("id", "text", "", "ID comanda"), ("date", "date", None, "Data comanda"),
    ("supplier", "text", "", "Furnizor"), ("pi_no", "text", "", "Nr. PI"),
    ("incoterm", "text", "DDP", "Incoterm"), ("transport_type", "text", "Aerian", "Tip transport"),
    ("goods_cur", "text", "USD", "Moneda marfa"), ("usd_ron", "num", None, "Curs USD→RON"),
    ("eur_ron", "num", None, "Curs EUR→RON"), ("transp_cur", "text", "USD", "Moneda transport"),
    ("transp_basis", "text", "Total fix", "Baza tarif transport"), ("transp_rate", "num", 0.0, "Tarif transport"),
    ("min_chargeable", "num", 0.0, "Minim taxabil (kg/CBM)"), ("volumetric", "text", "Nu", "Greutate volumetrica?"),
    ("insurance", "num", 0.0, "Asigurare (moneda transport)"), ("n_categories", "num", 0.0, "Nr. categorii"),
    ("flat_fee_eur", "num", 0.0, "Taxa forfetara EUR/categ."), ("n_parcels", "num", 1.0, "Nr. colete"),
    ("logistics_lei", "num", 0.0, "Taxa logistica RO lei/colet"), ("local_ron", "num", 0.0, "Broker/transport intern (RON)"),
    ("duty_pct", "num", None, "Taxa vamala %"), ("vat_pct", "num", None, "TVA import %"),
    ("alloc_method", "text", "Automat", "Metoda alocare"), ("status", "text", "Draft", "Status"),
    ("notes", "text", "", "Observatii"),
]
LINES = [
    ("order_id", "text", "", "ID comanda"), ("sku", "text", "", "SKU / Item"), ("description", "text", "", "Descriere"),
    ("hs_code", "text", "", "Cod NC/HS"), ("qty", "num", 0.0, "Cantitate"), ("unit_price", "num", 0.0, "Pret unitar"),
    ("unit_weight_kg", "num", 0.0, "Greutate/buc (kg)"), ("pcs_per_carton", "num", 0.0, "Buc/carton"),
    ("carton_l", "num", 0.0, "L carton (cm)"), ("carton_w", "num", 0.0, "l carton (cm)"), ("carton_h", "num", 0.0, "H carton (cm)"),
    ("cbm_per_pc", "num", 0.0, "CBM/buc (manual)"), ("ro_price", "num", None, "Pret RO cu TVA"), ("notes", "text", "", "Observatii"),
]
CATALOG = [
    ("sku", "text", "", "SKU"), ("description", "text", "", "Descriere"), ("hs_code", "text", "", "Cod NC/HS"),
    ("supplier", "text", "", "Furnizor"), ("currency", "text", "USD", "Moneda"), ("last_price", "num", None, "Ultimul pret"),
    ("unit_weight_kg", "num", None, "Greutate/buc (kg)"), ("pcs_per_carton", "num", None, "Buc/carton"),
    ("carton_l", "num", None, "L carton"), ("carton_w", "num", None, "l carton"), ("carton_h", "num", None, "H carton"),
    ("sell_price_vat", "num", None, "Pret vanzare cu TVA"), ("vat_pct", "num", 0.21, "TVA vanzare"),
    ("commission_pct", "num", 0.15, "Comision marketplace"), ("packaging", "num", 0.0, "Ambalare/buc"),
    ("courier", "num", 0.0, "Livrare curier/buc"), ("storage", "num", 0.0, "Depozitare/buc"),
    ("returns_pct", "num", 0.0, "Rata retur"), ("ads", "num", 0.0, "Ads/buc"),
    ("ro_price", "num", None, "Pret RO piata cu TVA"), ("notes", "text", "", "Observatii"),
]
HISTORY = [
    ("date", "date", None, "Data"), ("sku", "text", "", "SKU"), ("supplier", "text", "", "Furnizor"),
    ("pi_no", "text", "", "Nr. PI"), ("currency", "text", "", "Moneda"), ("unit_price", "num", None, "Pret unitar"),
    ("qty", "num", None, "Cantitate"), ("source", "text", "", "Sursa"),
]
SPECS = {"orders": ORDERS, "lines": LINES, "catalog": CATALOG, "history": HISTORY}
CURRENCIES = ["USD", "EUR", "RON"]
TRANSPORT_TYPES = ["Aerian", "Maritim LCL", "Maritim FCL", "Rutier", "Curier"]
BASES = ["kg", "CBM", "Total fix"]
METHODS = ["Automat", "Greutate", "Volum (CBM)", "Egal pe bucata", "Valoare marfa"]
STATUSES = ["Draft", "Plasata", "In tranzit", "Receptionata"]


def cols(name): return [c[0] for c in SPECS[name]]
def labels(name): return {c[0]: c[3] for c in SPECS[name]}
def kind(name, col): return {c[0]: c[1] for c in SPECS[name]}[col]


def parse_date(s):
    """Accepta ISO, dd.mm.yyyy sau obiecte data; returneaza Timestamp sau NaT."""
    return pd.to_datetime(s, errors="coerce", dayfirst=True, format="mixed")


def empty(name):
    return coerce(name, pd.DataFrame(columns=cols(name)))


def coerce(name, df):
    """Asigura toate coloanele, tipurile corecte si ordinea din schema."""
    df = df.copy()
    for col, k, default, _ in SPECS[name]:
        if col not in df.columns:
            df[col] = default if k != "date" else pd.NaT
        if k == "num":
            df[col] = pd.to_numeric(df[col], errors="coerce")
            if default is not None:
                df[col] = df[col].fillna(default)
        elif k == "date":
            df[col] = parse_date(df[col])
        else:
            df[col] = df[col].fillna(default).astype(str).replace({"nan": default, "None": default})
    return df[cols(name)].reset_index(drop=True)
