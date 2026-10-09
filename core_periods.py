"""Luni fiscale: costuri de import din comenzile lunii, vanzari (din 'Vandut'), OPEX, profit si inchiderea lunii."""
import json

import numpy as np
import pandas as pd

import core_margins as margins


def month_key(ts):
    return None if pd.isna(ts) else pd.Timestamp(ts).strftime("%Y-%m")


def available_months(orders, months, today=None):
    ms = set(orders["date"].dropna().dt.strftime("%Y-%m")) | set(months["month"][months["month"] != ""])
    ms.add(month_key(today or pd.Timestamp.today()))
    return sorted(ms)


def latest_closed(months):
    c = months[months["closed"] == "Da"]
    return None if c.empty else c["month"].max()


def snapshot_of(months):
    """Vandutul cumulat la ultima inchidere {sku_key: cantitate}."""
    last = latest_closed(months)
    if not last:
        return {}
    return json.loads(months.loc[months["month"] == last, "sold_snapshot"].iloc[0] or "{}")


def import_costs(orders_calc, lines_calc, month, include_draft=True):
    """Costurile de import ale comenzilor cu data in luna: marfa, transport, taxe vamale, TVA import, alte costuri."""
    o = orders_calc[orders_calc["date"].dt.strftime("%Y-%m") == month]
    if not include_draft:
        o = o[o["status"] != "Draft"]
    l = lines_calc[lines_calc["order_id"].isin(o["id"]) & lines_calc["valid"]]
    return {"orders": ", ".join(o["id"]), "goods_ron": float(o["goods_ron"].sum()), "transport_ron": float(o["transp_ron"].sum()),
            "duty_ron": float((l["duty_pc"] * l["qty"]).sum()), "vat_ron": float((l["vat_pc"] * l["qty"]).sum()),
            "local_ron": float((o["logistics_ron"] + o["local_ron"]).sum())}, o


def sales_in_month(mt, snapshot):
    """Vanzari din luna = 'Vandut' cumulat acum - 'Vandut' la ultima inchidere, valorizate cu pretul de vanzare si costurile din tabelul de marja."""
    t = mt.copy()
    t["_k"] = margins.sku_key(t["sku"])
    t["delta"] = t["sold_qty"].fillna(0) - t["_k"].map(snapshot).fillna(0)
    t = t[t["delta"] != 0]
    ok = t["sell_price_vat"].gt(0) & t["profit_vat"].notna() & t["profit_nonvat"].notna()
    u = t[ok]
    net = u["sell_price_vat"] / (1 + u["vat_pct"])
    res = {"revenue_nonvat": float((u["delta"] * u["sell_price_vat"]).sum()), "revenue_vat": float((u["delta"] * net).sum()),
           "sell_costs_vat": float((u["delta"] * u["sell_costs_vat"]).sum()), "sell_costs_nonvat": float((u["delta"] * u["sell_costs_nonvat"]).sum()),
           "cogs_vat": float((u["delta"] * u["cost_novat"]).sum()), "cogs_nonvat": float((u["delta"] * u["cost_vat"]).sum()),
           "gross_vat": float((u["delta"] * u["profit_vat"]).sum()), "gross_nonvat": float((u["delta"] * u["profit_nonvat"]).sum())}
    return res, t.assign(valoare=t["delta"] * t["sell_price_vat"], ok=ok)


def build_row(month, costs, sales, opex_df, mt, closed=False):
    """Randul lunii cu profit cash (cheltuielile lunii) si contabil (cost marfa vanduta)."""
    opex = float(opex_df["Suma"].fillna(0).sum())
    imp_vat = costs["goods_ron"] + costs["transport_ron"] + costs["duty_ron"] + costs["local_ron"]   # platitor TVA: TVA import se recupereaza
    imp_non = imp_vat + costs["vat_ron"]
    snap = {k: float(v) for k, v in zip(margins.sku_key(mt["sku"]), mt["sold_qty"].fillna(0))}
    return {"month": month, "closed": "Da" if closed else "Nu", "closed_at": pd.Timestamp.today().normalize() if closed else pd.NaT,
            "orders": costs["orders"], **{k: costs[k] for k in ("goods_ron", "transport_ron", "duty_ron", "vat_ron", "local_ron")}, "opex_ron": opex,
            "revenue_vat": sales["revenue_vat"], "revenue_nonvat": sales["revenue_nonvat"], "sell_costs_vat": sales["sell_costs_vat"],
            "sell_costs_nonvat": sales["sell_costs_nonvat"], "cogs_vat": sales["cogs_vat"], "cogs_nonvat": sales["cogs_nonvat"],
            "profit_cash_vat": sales["revenue_vat"] - imp_vat - sales["sell_costs_vat"] - opex,
            "profit_cash_nonvat": sales["revenue_nonvat"] - imp_non - sales["sell_costs_nonvat"] - opex,
            "profit_acc_vat": sales["gross_vat"] - opex, "profit_acc_nonvat": sales["gross_nonvat"] - opex,
            "opex_detail": json.dumps(dict(zip(opex_df["Categorie"], opex_df["Suma"].fillna(0))), ensure_ascii=False), "sold_snapshot": json.dumps(snap)}


def annual(months, basis="cash", project=False):
    """(ca_vat, profit_vat, ca_nonvat, profit_nonvat, nr_luni) din lunile INCHISE. project=True -> medie lunara x 12."""
    c = months[months["closed"] == "Da"]
    n = len(c)
    if n == 0:
        return 0.0, 0.0, 0.0, 0.0, 0
    f = 12 / n if project else 1.0
    pv, pn = ("profit_cash_vat", "profit_cash_nonvat") if basis == "cash" else ("profit_acc_vat", "profit_acc_nonvat")
    return (c["revenue_vat"].sum() * f, c[pv].sum() * f, c["revenue_nonvat"].sum() * f, c[pn].sum() * f, n)
