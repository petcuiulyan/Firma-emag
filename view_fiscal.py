"""P&L lunar, OPEX si comparatia celor 4 regimuri fiscale."""
import pandas as pd
import plotly.express as px
import streamlit as st

import core_fiscal as fiscal
import core_margins as margins
import core_storage as storage
import view_common as c


def render():
    st.title("🏛️ Fiscal: P&L și regim recomandat")
    d, s, oc, lc = c.compute_all()
    mt = margins.margin_table(d["catalog"][d["catalog"]["sku"] != ""], margins.weighted_costs(lc, oc), s["min_margin"])
    mv, mn = margins.portfolio(mt)
    st.caption("Estimează veniturile lunare; marja medie vine din **Marjă per produs**, iar OPEX-ul din tabelul de mai jos. Simulare de planificare – nu consultanță fiscală.")
    t1, t2, t3 = st.tabs(["Venituri & P&L", "OPEX lunar", "Comparație regimuri"])
    with t1:
        mv_in = st.number_input("Marjă medie SRL TVA (override)", value=0.0 if mv != mv else float(mv), format="%.4f", help="Se preia din Marjă per produs; o poți ajusta.")
        mn_in = st.number_input("Marjă medie SRL non-TVA (override)", value=0.0 if mn != mn else float(mn), format="%.4f")
        rev = pd.DataFrame({"Luna": fiscal.MONTHS, "Venit TVA (fără TVA)": s["revenue_vat"], "Venit non-TVA": s["revenue_nonvat"]})
        ed = st.data_editor(rev, hide_index=True, width="stretch", disabled=["Luna"], key="rev_ed")
        if st.button("💾 Salvează veniturile"):
            s["revenue_vat"] = ed["Venit TVA (fără TVA)"].fillna(0).tolist(); s["revenue_nonvat"] = ed["Venit non-TVA"].fillna(0).tolist()
            storage.save_settings(s); st.success("Salvat."); st.rerun()
    opex = fiscal.opex_monthly(s["opex"])
    with t2:
        o = st.data_editor(pd.DataFrame(s["opex"], columns=["Categorie", "Minim (lei/lună)", "Maxim (lei/lună)"]), num_rows="dynamic", hide_index=True, width="stretch", key="opex_ed")
        st.metric("OPEX lunar folosit în P&L (medie min/max)", f"{fiscal.opex_monthly(o.fillna(0).values.tolist()):,.0f} lei")
        if st.button("💾 Salvează OPEX"):
            s["opex"] = o.fillna(0).values.tolist(); storage.save_settings(s); st.success("Salvat."); st.rerun()
    pl_v = fiscal.monthly_pl(ed["Venit TVA (fără TVA)"].fillna(0), mv_in, opex)
    pl_n = fiscal.monthly_pl(ed["Venit non-TVA"].fillna(0), mn_in, opex)
    with t1:
        st.plotly_chart(px.line(pd.DataFrame({"Luna": fiscal.MONTHS, "SRL TVA": pl_v["Profit brut"], "SRL non-TVA": pl_n["Profit brut"]}).melt("Luna"),
                                x="Luna", y="value", color="variable", markers=True, title="Profit brut lunar"), width="stretch")
    with t3:
        ca_v, ca_n = pl_v["Venit"].sum(), pl_n["Venit"].sum()
        th = fiscal.thresholds(ca_v, ca_n, s)
        st.info(f"Plafon TVA ({s['vat_threshold']:,.0f} lei): {th['tva']}  \nPlafon micro (≈{th['micro_ron']:,.0f} lei): {th['micro']}")
        df, best = fiscal.compare(ca_v, pl_v["Profit brut"].sum(), ca_n, pl_n["Profit brut"].sum(), s)
        st.plotly_chart(px.bar(df[df["Scenariu"] == 0.0], x="Regim", y="Profit net", title="Profit net anual la prețul de bază"), width="stretch")
        pv = df.pivot(index="Regim", columns="Scenariu", values="Profit net")
        pv.columns = [f"{x:+.0%}" for x in pv.columns]
        st.dataframe(pv.style.format("{:,.0f}"), width="stretch")
        base = best[best["Scenariu"] == 0.0].iloc[0]
        st.success(f"Regim cu cel mai mare profit net (preț de bază): **{base['Regim']}** – {base['Profit net']:,.0f} lei")
