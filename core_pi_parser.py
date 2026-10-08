"""Citeste fisiere PI ale furnizorilor (xlsx/xls/csv), detecteaza antetul si coloanele, normalizeaza liniile."""
import re

import numpy as np
import pandas as pd

SYNONYMS = {
    "sku": ["item no", "item number", "item", "model", "sku", "article", "product code", "part no", "ref", "code", "cod"],
    "description": ["description", "product name", "item name", "goods", "descriere", "name", "product"],
    "qty": ["quantity", "qty", "order qty", "pcs", "units", "cantitate"],
    "unit_price": ["unit price", "u/p", "price/pc", "unit cost", "fob", "price", "pret"],
    "amount": ["total amount", "amount", "total", "value", "valoare"],
    "weight": ["net weight", "n.w", "nw", "g.w", "gw", "weight", "greutate"],
    "ppc": ["pcs/ctn", "pcs per carton", "qty/ctn", "pcs/carton", "units/ctn", "packing", "buc/carton", "per carton"],
    "cartons": ["no of ctn", "cartons", "ctns", "ctn", "nr cutii"],
    "size": ["carton size", "ctn size", "size", "measurement", "meas", "dimension", "carton dimension"],
    "hs": ["hs code", "hs", "customs code", "tariff", "nc"],
}
FIELD_LABELS = {"sku": "SKU / Item no.", "description": "Descriere", "qty": "Cantitate", "unit_price": "Pret unitar", "amount": "Valoare totala (optional)",
                "weight": "Greutate (kg)", "ppc": "Buc / carton", "cartons": "Nr. cartoane (optional)", "size": "Dimensiuni carton (L*l*H)", "hs": "Cod NC/HS"}


def _norm(x):
    return re.sub(r"[^a-z0-9/ ]+", " ", str(x).lower()).replace("  ", " ").strip()


def _score(cell, syn):
    c, s = _norm(cell), _norm(syn)
    if not c: return 0
    if c == s: return 30 + len(s)
    if c.startswith(s) or c.endswith(s): return 20 + len(s)
    if len(s) >= 3 and s in c: return 10 + len(s)
    return 0


def read_raw(file, sheet=None):
    name = getattr(file, "name", str(file)).lower()
    if name.endswith(".csv"):
        return {"csv": pd.read_csv(file, header=None, dtype=object, sep=None, engine="python")}
    xl = pd.ExcelFile(file)
    return {sh: xl.parse(sh, header=None, dtype=object) for sh in ([sheet] if sheet else xl.sheet_names)}


def detect_header(raw, max_rows=40):
    best, best_n = 0, -1
    for i in range(min(max_rows, len(raw))):
        n = sum(1 for v in raw.iloc[i] if any(_score(v, syn) for syns in SYNONYMS.values() for syn in syns))
        if n > best_n: best, best_n = i, n
    return best


def auto_map(columns):
    """Atribuie fiecarui camp coloana cu cel mai bun scor (o coloana se foloseste o singura data)."""
    cand = sorted(((max((_score(c, syn) for syn in syns), default=0), f, i) for f, syns in SYNONYMS.items() for i, c in enumerate(columns)), reverse=True)
    mapping, used = {}, set()
    for sc, f, i in cand:
        if sc > 0 and f not in mapping and i not in used:
            mapping[f] = i; used.add(i)
    return mapping


def with_header(raw, header_row):
    df = raw.iloc[header_row + 1:].copy()
    df.columns = [str(c).strip() if str(c) != "nan" else f"col{i}" for i, c in enumerate(raw.iloc[header_row])]
    return df.dropna(how="all").reset_index(drop=True)


_DIM = re.compile(r"(\d+(?:[.,]\d+)?)\s*[x*×X]\s*(\d+(?:[.,]\d+)?)\s*[x*×X]\s*(\d+(?:[.,]\d+)?)")


def parse_dims(v):
    m = _DIM.search(str(v))
    return tuple(float(g.replace(",", ".")) for g in m.groups()) if m else (np.nan,) * 3


def _num(s): return pd.to_numeric(s.astype(str).str.replace(",", "").str.extract(r"(-?\d+\.?\d*)")[0], errors="coerce")


def normalize(df, mapping, weight_basis="per bucata", dim_unit="cm"):
    """mapping: camp -> nume coloana. weight_basis: 'per bucata' | 'per carton' | 'total linie'."""
    g = lambda f: df[mapping[f]] if mapping.get(f) in df.columns else pd.Series([np.nan] * len(df), index=df.index)
    txt = lambda f: g(f).fillna("").astype(str).str.strip().replace("nan", "")
    out = pd.DataFrame({"sku": txt("sku"), "description": txt("description"),
                        "hs_code": txt("hs"), "qty": _num(g("qty")),
                        "unit_price": _num(g("unit_price")), "pcs_per_carton": _num(g("ppc"))})
    amount, cartons = _num(g("amount")), _num(g("cartons"))
    out["unit_price"] = out["unit_price"].fillna(amount / out["qty"].replace(0, np.nan))
    w = _num(g("weight"))
    if weight_basis == "per carton":
        w = w / out["pcs_per_carton"].replace(0, np.nan)
    elif weight_basis == "total linie":
        w = w / out["qty"].replace(0, np.nan)
    out["unit_weight_kg"] = w
    dims = g("size").map(parse_dims)
    k = {"cm": 1.0, "mm": 0.1, "m": 100.0}[dim_unit]
    for i, c in enumerate(("carton_l", "carton_w", "carton_h")):
        out[c] = dims.map(lambda t: t[i]) * k
    out["pcs_per_carton"] = out["pcs_per_carton"].fillna(out["qty"] / cartons.replace(0, np.nan))
    out = out[(out["qty"] > 0) & (out["sku"] != "")]
    out = out[~out["sku"].str.lower().str.contains("total")]
    return out.reset_index(drop=True)
