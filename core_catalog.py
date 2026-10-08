"""Catalog produse + istoric preturi + compararea unui PI nou cu ce stim deja."""
import numpy as np
import pandas as pd

import core_schema as schema

COMPARE_FIELDS = ["unit_weight_kg", "pcs_per_carton", "carton_l", "carton_w", "carton_h"]


def key(s): return s.astype(str).str.strip().str.upper()


def compare(pi, catalog, tol_price=0.01, tol_data=0.05):
    """Compara liniile PI cu catalogul: NOU / PRET SCHIMBAT / DATE DIFERITE / NESCHIMBAT."""
    cat = catalog.assign(_k=key(catalog["sku"])).drop_duplicates("_k").set_index("_k")
    rows = []
    for _, r in pi.iterrows():
        k = str(r["sku"]).strip().upper()
        if k not in cat.index:
            rows.append({"sku": r["sku"], "status": "NOU", "prev_price": np.nan, "delta_pct": np.nan, "data_diff": ""}); continue
        c = cat.loc[k]
        prev = c["last_price"]
        delta = (r["unit_price"] - prev) / prev if prev and prev == prev else np.nan
        diffs = [f for f in COMPARE_FIELDS if r[f] == r[f] and c[f] == c[f] and c[f] > 0 and abs(r[f] - c[f]) / c[f] > tol_data]
        status = "PRET SCHIMBAT" if (delta == delta and abs(delta) > tol_price) else ("DATE DIFERITE" if diffs else "NESCHIMBAT")
        rows.append({"sku": r["sku"], "status": status, "prev_price": prev, "delta_pct": delta, "data_diff": ", ".join(diffs)})
    return pi.merge(pd.DataFrame(rows), on="sku", how="left")


def apply_to_catalog(pi, catalog, supplier, currency, selected_skus):
    """Adauga produsele noi si actualizeaza (pret, greutate, dimensiuni) pe cele existente selectate."""
    cat = catalog.copy()
    cat["_k"] = key(cat["sku"])
    n_new = n_upd = 0
    fields = ["description", "hs_code", "unit_price", *COMPARE_FIELDS]
    for _, r in pi[pi["sku"].isin(selected_skus)].iterrows():
        k = str(r["sku"]).strip().upper()
        vals = {"sku": r["sku"], "supplier": supplier, "currency": currency, "last_price": r["unit_price"]}
        for f in fields:
            if f != "unit_price" and r[f] == r[f] and str(r[f]) not in ("", "nan"):
                vals[f] = r[f]
        if (cat["_k"] == k).any():
            idx = cat.index[cat["_k"] == k][0]
            for f, v in vals.items(): cat.loc[idx, f] = v
            n_upd += 1
        else:
            cat = pd.concat([cat, pd.DataFrame([{**vals, "_k": k}])], ignore_index=True); n_new += 1
    return schema.coerce("catalog", cat.drop(columns="_k")), n_new, n_upd


def history_rows(pi, supplier, pi_no, date, currency, source="PI import"):
    h = pd.DataFrame({"date": date, "sku": pi["sku"], "supplier": supplier, "pi_no": pi_no, "currency": currency,
                      "unit_price": pi["unit_price"], "qty": pi["qty"], "source": source})
    return schema.coerce("history", h)


def lines_from_pi(pi, order_id):
    l = pi[["sku", "description", "hs_code", "qty", "unit_price", "unit_weight_kg", "pcs_per_carton", "carton_l", "carton_w", "carton_h"]].copy()
    l["order_id"] = order_id
    return schema.coerce("lines", l)


def next_order_id(orders):
    nums = pd.to_numeric(orders["id"].str.extract(r"(\d+)")[0], errors="coerce").dropna()
    return f"C{int(nums.max()) + 1 if len(nums) else 1:03d}"
