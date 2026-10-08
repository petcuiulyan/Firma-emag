"""Comenzi existente: editeaza antetul (data, curs, transport) si liniile; sumar pe comenzi."""
import pandas as pd
import streamlit as st

import core_schema as schema
import core_storage as storage
import view_common as c
from view_order_form import order_form


def render():
    st.title("🧾 Comenzi")
    d, s, oc, lc = c.compute_all()
    if oc.empty:
        c.info_empty("Nicio comandă. Creeaz-o din **Comandă nouă** sau din **Produse & PI**."); return
    cols = ["id", "date", "supplier", "status", "transport_type", "transp_basis", "usd_ron", "eur_ron", "qty_tot", "w_tot", "v_tot", "transp_ron",
            "ron_per_kg", "ron_per_cbm", "total_novat_ron", "total_vat_ron", "warnings"]
    st.dataframe(oc.sort_values("date", ascending=False)[cols], hide_index=True, width="stretch", column_config={
        **c.column_config("orders"), "qty_tot": "Bucăți", "w_tot": st.column_config.NumberColumn("kg", format="%.1f"), "v_tot": st.column_config.NumberColumn("CBM", format="%.3f"),
        "transp_ron": st.column_config.NumberColumn("Transport RON", format="%.0f"), "ron_per_kg": st.column_config.NumberColumn("RON/kg", format="%.2f"),
        "ron_per_cbm": st.column_config.NumberColumn("RON/CBM", format="%.0f"), "total_novat_ron": st.column_config.NumberColumn("Total fără TVA", format="%.0f"),
        "total_vat_ron": st.column_config.NumberColumn("Total cu TVA", format="%.0f"), "warnings": "Avertismente"})
    st.divider()
    oid = st.selectbox("Editează comanda", oc["id"].tolist())
    row = d["orders"][d["orders"]["id"] == oid].iloc[0].to_dict()
    st.subheader("Antet")
    new = order_form(row, s, f"ed_{oid}", id_locked=True)
    new["id"] = oid
    if st.button("💾 Salvează antetul", type="primary"):
        o = d["orders"]; o.loc[o["id"] == oid, list(new)] = list(new.values())
        storage.save("orders", o); st.success("Antet salvat."); st.rerun()
    st.subheader("Linii produs")
    mine = d["lines"][d["lines"]["order_id"] == oid]
    edited = st.data_editor(mine, num_rows="dynamic", hide_index=True, width="stretch", key=f"ln_{oid}", column_config=c.column_config("lines", hide=("order_id",)))
    b = st.columns([1, 1, 3])
    if b[0].button("💾 Salvează liniile"):
        rest = d["lines"][d["lines"]["order_id"] != oid]
        storage.save("lines", pd.concat([rest, schema.coerce("lines", edited.assign(order_id=oid))], ignore_index=True)); st.success("Linii salvate."); st.rerun()
    with b[1].popover("🗑️ Șterge comanda"):
        if st.button("Confirm ștergerea", type="primary"):
            storage.save("orders", d["orders"][d["orders"]["id"] != oid]); storage.save("lines", d["lines"][d["lines"]["order_id"] != oid]); st.rerun()
