"""Marja per SKU: varianta SRL platitor TVA vs neplatitor TVA (foaia 'Marja per Produs')."""
import numpy as np
import pandas as pd


def weighted_costs(lines_calc, orders_calc, include_status=("Plasata", "In tranzit", "Receptionata")):
    """Cost mediu ponderat pe SKU (fara TVA si cash cu TVA) din comenzile nefinalizate ca Draft."""
    ok = orders_calc.loc[orders_calc["status"].isin(include_status), "id"]
    l = lines_calc[lines_calc["order_id"].isin(ok) & lines_calc["valid"]]
    g = l.groupby("sku").agg(qty=("qty", "sum"), novat=("total_novat_ron", "sum"), vat=("total_vat_ron", "sum"))
    g["cost_novat"] = g["novat"] / g["qty"]
    g["cost_vat"] = g["vat"] / g["qty"]
    return g[["qty", "cost_novat", "cost_vat"]]


def margin_table(catalog, costs, min_margin):
    c = catalog[catalog["sku"].str.strip() != ""].merge(costs, left_on="sku", right_index=True, how="left")
    extra = c["packaging"] + c["courier"] + c["storage"] + c["ads"]
    net_price = c["sell_price_vat"] / (1 + c["vat_pct"])
    c["profit_vat"] = net_price - c["cost_novat"] - c["sell_price_vat"] * c["commission_pct"] - extra - c["returns_pct"] * (c["cost_novat"] + extra)
    c["margin_vat"] = c["profit_vat"] / net_price.replace(0, np.nan)
    c["profit_nonvat"] = c["sell_price_vat"] - c["cost_vat"] - c["sell_price_vat"] * c["commission_pct"] - extra - c["returns_pct"] * (c["cost_vat"] + extra)
    c["margin_nonvat"] = c["profit_nonvat"] / c["sell_price_vat"].replace(0, np.nan)
    c["diff"] = c["profit_vat"] - c["profit_nonvat"]
    c["better"] = np.where(c["diff"].isna(), "", np.where(c["diff"] > 0, "SRL TVA", "SRL non-TVA"))
    c["below_min"] = np.where(c["margin_vat"].isna() | c["margin_nonvat"].isna(), "",
                              np.where((c["margin_vat"] < min_margin) & (c["margin_nonvat"] < min_margin), "DA - verifica", "OK"))
    return c


def portfolio(c):
    """Marja medie ponderata cu cantitatea (SRL TVA, SRL non-TVA)."""
    c = c.dropna(subset=["profit_vat", "profit_nonvat", "qty"])
    if c.empty or c["qty"].sum() == 0:
        return np.nan, np.nan
    mv = (c["profit_vat"] * c["qty"]).sum() / ((c["sell_price_vat"] / (1 + c["vat_pct"])) * c["qty"]).sum()
    mn = (c["profit_nonvat"] * c["qty"]).sum() / (c["sell_price_vat"] * c["qty"]).sum()
    return mv, mn
