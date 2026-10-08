"""Cost per bucata (RON / EUR / USD) si comparatie cu preturile din Romania."""
import numpy as np
import pandas as pd
import streamlit as st

import view_common as c


def render():
    st.title("💶 Cost per bucată")
    d, s, oc, lc = c.compute_all()
    if lc.empty:
        c.info_empty("Nu există linii de comandă."); return
    ids = st.multiselect("Comenzi", oc["id"].tolist(), default=oc["id"].tolist())
    v = lc[lc["order_id"].isin(ids)]
    t1, t2, t3 = st.tabs(["Cost final pe bucată", "Detaliu calcul", "Comparație piață RO"])
    money = lambda t: st.column_config.NumberColumn(t, format="%.2f")
    with t1:
        st.caption("**Fără TVA** = cost real dacă firma e plătitoare de TVA (TVA-ul de import se recuperează). **Cu TVA** = cost real cash pentru neplătitor.")
        tbl = v[["order_id", "o_date", "sku", "description", "qty", "cost_novat_ron", "cost_novat_eur", "cost_novat_usd",
                 "cost_vat_ron", "cost_vat_eur", "cost_vat_usd", "total_novat_ron", "total_vat_ron", "status_line"]]
        st.dataframe(tbl, hide_index=True, width="stretch", column_config={
            "order_id": "Comandă", "o_date": st.column_config.DateColumn("Data", format="DD.MM.YYYY"), "sku": "SKU", "description": "Descriere", "qty": "Cant.",
            "cost_novat_ron": money("Fără TVA RON"), "cost_novat_eur": money("Fără TVA EUR"), "cost_novat_usd": money("Fără TVA USD"),
            "cost_vat_ron": money("Cu TVA RON"), "cost_vat_eur": money("Cu TVA EUR"), "cost_vat_usd": money("Cu TVA USD"),
            "total_novat_ron": money("Total linie fără TVA"), "total_vat_ron": money("Total linie cu TVA"), "status_line": "Status"})
        m = st.columns(3)
        m[0].metric("Total fără TVA (RON)", f"{v['total_novat_ron'].sum():,.0f}")
        m[1].metric("Total cu TVA (RON)", f"{v['total_vat_ron'].sum():,.0f}")
        m[2].metric("TVA import (RON)", f"{(v['total_vat_ron'] - v['total_novat_ron']).sum():,.0f}")
        st.download_button("⬇️ Export Excel", c.to_xlsx({"Cost per bucata": tbl}), "cost_per_bucata.xlsx")
    with t2:
        det = v[["order_id", "sku", "qty", "price_ron", "transport_pc", "cif_pc", "duty_pc", "vat_base_pc", "vat_pc", "local_pc", "share"]]
        st.dataframe(det, hide_index=True, width="stretch", column_config={
            "order_id": "Comandă", "sku": "SKU", "qty": "Cant.", "price_ron": money("Preț marfă/buc"), "transport_pc": money("Transport+asig./buc"),
            "cif_pc": money("Valoare vamă CIF/buc"), "duty_pc": money("Taxă vamală/buc"), "vat_base_pc": money("Bază TVA/buc"), "vat_pc": money("TVA import/buc"),
            "local_pc": money("Taxe locale/buc"), "share": st.column_config.NumberColumn("Cotă alocare", format="percent")})
        st.caption("Valori în RON pe bucată. Baza TVA = CIF + taxe vamale; taxa logistică RO și brokerul nu intră în baza TVA.")
    with t3:
        vat_payer = st.toggle("Firma este plătitoare de TVA", value=s["vat_payer"], help="Plătitor: compară prețul RO fără TVA cu costul fără TVA. Neplătitor: preț RO cu TVA vs cost cu TVA.")
        cat = d["catalog"].drop_duplicates("sku").set_index("sku")["ro_price"]
        ro = v["ro_price"].fillna(v["sku"].map(cat))
        cost = v["cost_novat_ron"] if vat_payer else v["cost_vat_ron"]
        price = ro / (1 + v["vat_rate"]) if vat_payer else ro
        out = pd.DataFrame({"Comandă": v["order_id"], "SKU": v["sku"], "Descriere": v["description"], "Cost referință": cost, "Preț RO referință": price})
        out["Diferență"] = out["Preț RO referință"] - out["Cost referință"]
        out["Diferență %"] = out["Diferență"] / out["Preț RO referință"]
        thr = 1 + s["min_margin"]
        out["Verdict"] = np.select([out["Cost referință"].isna(), out["Preț RO referință"].isna(), out["Preț RO referință"] > out["Cost referință"] * thr,
                                    out["Preț RO referință"] > out["Cost referință"]],
                                   ["Date incomplete", "Introdu prețul RO (Catalog sau linia comenzii)", "Import avantajos – marjă bună", "Import ușor avantajos – marjă mică"],
                                   "Piața RO mai ieftină – verifică")
        st.dataframe(out, hide_index=True, width="stretch", column_config={
            "Cost referință": money("Cost referință (RON)"), "Preț RO referință": money("Preț RO referință (RON)"), "Diferență": money("Diferență (RON)"),
            "Diferență %": st.column_config.NumberColumn(format="percent")})
        st.caption("Prețul RO se completează în **Produse & PI → Catalog** (coloana „Preț RO piață cu TVA”) sau pe linia comenzii.")
