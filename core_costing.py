"""Motorul de cost per bucata: aceeasi logica ca foile 'Comenzi' + 'Calculator Cost per Bucata' din Excel.

Flux per comanda:  marfa (RON) + transport/asigurare (alocat) = valoare in vama (CIF)
                   + taxa vamala (% din CIF + taxa forfetara) = baza TVA  ->  TVA import
                   + costuri locale (taxa logistica RO + broker) – NU intra in baza TVA
Cost final: fara TVA (recuperabil pt. platitor de TVA) si cash cu TVA (pt. neplatitor), in RON / EUR / USD.
"""
import numpy as np
import pandas as pd

FX_OK = ("USD", "EUR", "RON")


def fx(cur, usd, eur):
    """Cursul RON pentru o moneda (RON = 1)."""
    return np.where(cur == "USD", usd, np.where(cur == "EUR", eur, 1.0))


def cbm_per_piece(lines):
    manual = lines["cbm_per_pc"].fillna(0)
    dims = lines["carton_l"] * lines["carton_w"] * lines["carton_h"]
    auto = np.where((dims > 0) & (lines["pcs_per_carton"] > 0), dims / 1e6 / lines["pcs_per_carton"].replace(0, np.nan), 0.0)
    return np.where(manual > 0, manual, np.nan_to_num(auto))


def _method(o):
    chosen = np.where(o["alloc_method"].isin(["", "Automat"]), np.where(o["transp_basis"] == "CBM", "Volum (CBM)", "Greutate"), o["alloc_method"])
    ok = ((chosen == "Greutate") & (o["w_tot"] > 0)) | ((chosen == "Volum (CBM)") & (o["v_tot"] > 0)) | ((chosen == "Valoare marfa") & (o["val_tot"] > 0))
    eff = np.where(ok, chosen, "Egal pe bucata")
    key = np.select([eff == "Greutate", eff == "Volum (CBM)", eff == "Valoare marfa"], [o["w_tot"], o["v_tot"], o["val_tot"]], o["qty_tot"])
    return chosen, eff, key


def compute(orders, lines, s):
    """Returneaza (orders_calc, lines_calc). Nu modifica datele de intrare."""
    o = orders.copy()
    l = lines.copy()
    l = l[(l["sku"].str.strip() != "") | (l["qty"] > 0)].reset_index(drop=True)
    l["cbm_pc"] = cbm_per_piece(l)
    l["w_line"] = l["qty"] * l["unit_weight_kg"]
    l["v_line"] = l["qty"] * l["cbm_pc"]
    l["val_line"] = l["qty"] * l["unit_price"]
    agg = l.groupby("order_id").agg(n_lines=("qty", lambda x: int((x > 0).sum())), qty_tot=("qty", "sum"), w_tot=("w_line", "sum"),
                                    v_tot=("v_line", "sum"), val_tot=("val_line", "sum"))
    o = o.merge(agg, left_on="id", right_index=True, how="left")
    for c in agg.columns:
        o[c] = o[c].fillna(0)
    usd, eur = o["usd_ron"].fillna(0), o["eur_ron"].fillna(0)
    o["goods_ron"] = o["val_tot"] * fx(o["goods_cur"], usd, eur)
    o["vol_weight"] = np.where(o["volumetric"] == "Da", o["v_tot"] * 1e6 / s["vol_divisor"], 0.0)
    o["chargeable"] = np.select(
        [o["transp_basis"] == "CBM", o["transp_basis"] == "kg"],
        [np.maximum(o["v_tot"], o["min_chargeable"]), np.maximum.reduce([o["w_tot"], o["vol_weight"], o["min_chargeable"]])], 1.0)
    o["transp_cur_total"] = np.where(o["transp_basis"] == "Total fix", o["transp_rate"], o["transp_rate"] * o["chargeable"]) + o["insurance"]
    o["transp_ron"] = o["transp_cur_total"] * fx(o["transp_cur"], usd, eur)
    o["ron_per_kg"] = np.where(o["w_tot"] > 0, o["transp_ron"] / o["w_tot"].replace(0, np.nan), np.nan)
    o["ron_per_cbm"] = np.where(o["v_tot"] > 0, o["transp_ron"] / o["v_tot"].replace(0, np.nan), np.nan)
    o["flat_ron"] = o["n_categories"] * o["flat_fee_eur"] * eur
    o["logistics_ron"] = o["n_parcels"] * o["logistics_lei"]
    o["method_chosen"], o["method_eff"], o["alloc_total"] = _method(o)

    warn = []
    for _, r in o.iterrows():
        w = []
        if not r["usd_ron"] > 0: w.append("Lipseste cursul USD")
        if not r["eur_ron"] > 0: w.append("Lipseste cursul EUR")
        if r["n_lines"] == 0: w.append("Nicio linie de produs")
        if r["goods_cur"] not in FX_OK or r["transp_cur"] not in FX_OK: w.append("Moneda marfa/transport lipsa")
        if r["transp_basis"] == "CBM" and r["v_tot"] == 0: w.append("Tarif pe CBM dar lipsesc dimensiunile")
        if r["transp_basis"] == "kg" and r["w_tot"] == 0: w.append("Tarif pe kg dar lipsesc greutatile")
        if r["method_chosen"] != r["method_eff"]: w.append("Cheie alocare lipsa: costurile se impart egal pe bucata")
        warn.append("; ".join(w) if w else "OK")
    o["warnings"] = warn

    oc = o.set_index("id")
    l = l.join(oc[["date", "usd_ron", "eur_ron", "goods_cur", "duty_pct", "vat_pct", "transp_ron", "flat_ron", "logistics_ron", "local_ron",
                   "method_eff", "alloc_total", "qty_tot", "warnings", "supplier"]].add_prefix("o_"), on="order_id")
    l["valid"] = l["o_goods_cur"].isin(FX_OK) & (l["qty"] > 0) & (l["o_usd_ron"] > 0) & (l["o_eur_ron"] > 0)
    l["key"] = np.select([l["o_method_eff"] == "Greutate", l["o_method_eff"] == "Volum (CBM)", l["o_method_eff"] == "Valoare marfa"],
                         [l["w_line"], l["v_line"], l["val_line"]], l["qty"])
    l["share"] = np.where(l["o_alloc_total"] > 0, l["key"] / l["o_alloc_total"].replace(0, np.nan), 0.0)
    q = l["qty"].replace(0, np.nan)
    hs = pd.Series(s.get("hs_duties", {}))
    l["duty_rate"] = l["hs_code"].map(hs).fillna(l["o_duty_pct"]).fillna(s["default_duty"])
    l["vat_rate"] = l["o_vat_pct"].fillna(s["vat_std"])
    l["price_ron"] = l["unit_price"] * fx(l["o_goods_cur"], l["o_usd_ron"], l["o_eur_ron"])
    l["transport_pc"] = l["o_transp_ron"] * l["share"] / q
    l["cif_pc"] = l["price_ron"] + l["transport_pc"]
    l["duty_pc"] = l["cif_pc"] * l["duty_rate"] + l["o_flat_ron"] * l["share"] / q
    l["vat_base_pc"] = l["cif_pc"] + l["duty_pc"]
    l["vat_pc"] = l["vat_base_pc"] * l["vat_rate"]
    l["local_pc"] = (l["o_logistics_ron"] + l["o_local_ron"]) * l["share"] / q
    l["cost_novat_ron"] = l["vat_base_pc"] + l["local_pc"]
    l["cost_vat_ron"] = l["cost_novat_ron"] + l["vat_pc"]
    calc_cols = ["price_ron", "transport_pc", "cif_pc", "duty_pc", "vat_base_pc", "vat_pc", "local_pc", "cost_novat_ron", "cost_vat_ron"]
    l.loc[~l["valid"], calc_cols] = np.nan
    for tag in ("novat", "vat"):
        l[f"cost_{tag}_eur"] = l[f"cost_{tag}_ron"] / l["o_eur_ron"].replace(0, np.nan)
        l[f"cost_{tag}_usd"] = l[f"cost_{tag}_ron"] / l["o_usd_ron"].replace(0, np.nan)
        l[f"total_{tag}_ron"] = l[f"cost_{tag}_ron"] * l["qty"]
    l["status_line"] = np.where(l["valid"], np.where(l["o_warnings"] == "OK", "OK", "Avertisment: " + l["o_warnings"].astype(str)),
                                "Date incomplete (comanda/curs/cantitate)")

    tot = l.groupby("order_id")[["total_novat_ron", "total_vat_ron"]].sum()
    o = o.join(tot, on="id").fillna({"total_novat_ron": 0, "total_vat_ron": 0})
    o["total_vat_amt"] = o["total_vat_ron"] - o["total_novat_ron"]
    o["total_vat_eur"] = o["total_vat_ron"] / usd_safe(o["eur_ron"])
    o["total_vat_usd"] = o["total_vat_ron"] / usd_safe(o["usd_ron"])
    return o, l


def usd_safe(x):
    return x.replace(0, np.nan)


def reference_cost(lines_calc, vat_payer):
    """Cost de referinta pentru comparatii: fara TVA daca firma e platitoare, altfel cash cu TVA."""
    return lines_calc["cost_novat_ron"] if vat_payer else lines_calc["cost_vat_ron"]
