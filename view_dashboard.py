"""Prezentare generala: KPI-uri si grafice."""
import pandas as pd
import plotly.express as px
import streamlit as st

import core_fiscal as fiscal
import core_margins as margins
import view_common as c


def render():
    st.title("📊 Prezentare generală")
    d, s, oc, lc = c.compute_all()
    done = oc[oc["status"] != "Draft"]
    if oc.empty:
        st.info("Nu există comenzi. Începe din **Comandă nouă** sau încarcă un PI în **Produse & PI**. "
                "Poți importa și calculatorul Excel existent din **Setări & Backup**.")
        return
    k = st.columns(4)
    k[0].metric("Comenzi (fără Draft)", len(done))
    k[1].metric("Bucăți importate", f"{done['qty_tot'].sum():,.0f}")
    k[2].metric("Valoare marfă (RON)", f"{done['goods_ron'].sum():,.0f}")
    k[3].metric("Cost total cu TVA (RON)", f"{done['total_vat_ron'].sum():,.0f}")
    costs = margins.weighted_costs(lc, oc)
    mt = margins.margin_table(d["catalog"], costs, s["min_margin"])
    mv, mn = margins.portfolio(mt)
    k = st.columns(4)
    k[0].metric("SKU în catalog", int((d["catalog"]["sku"] != "").sum()))
    k[1].metric("Marjă medie – SRL TVA", "–" if mv != mv else f"{mv:.1%}")
    k[2].metric("Marjă medie – non-TVA", "–" if mn != mn else f"{mn:.1%}")
    ca = sum(s["revenue_vat"])
    k[3].metric("CA anuală proiectată", f"{ca:,.0f} RON")
    if s["vat_threshold"] and max(ca, sum(s["revenue_nonvat"])) > 0.8 * s["vat_threshold"]:
        st.warning("CA proiectată se apropie de plafonul de TVA – verifică **Fiscal**.")

    a, b = st.columns(2)
    o = oc.dropna(subset=["date"]).sort_values("date")
    if not o.empty:
        f = px.line(o, x="date", y=["ron_per_kg", "ron_per_cbm"], markers=True, title="Cost transport: RON/kg și RON/CBM, comandă cu comandă")
        a.plotly_chart(f, width="stretch")
        o = o.assign(cumul=o["total_novat_ron"].cumsum())
        b.plotly_chart(px.area(o, x="date", y="cumul", title="Cost cumulat (fără TVA, RON)"), width="stretch")
    mt = mt.dropna(subset=["margin_vat"])
    if not mt.empty:
        m = mt.melt(id_vars="sku", value_vars=["margin_vat", "margin_nonvat"], var_name="Variantă", value_name="Marjă")
        st.plotly_chart(px.bar(m, x="sku", y="Marjă", color="Variantă", barmode="group", title="Marjă netă per SKU"), width="stretch")
    bad = oc[oc["warnings"] != "OK"]
    if not bad.empty:
        st.subheader("Comenzi cu avertismente")
        st.dataframe(bad[["id", "supplier", "warnings"]], hide_index=True, width="stretch")
