"""Capacitate transport: cutii -> paleti -> camion / container / avion."""
import streamlit as st

import core_capacity as capacity
import view_common as c


def render():
    st.title("🚚 Capacitate transport")
    d, s, oc, lc = c.compute_all()
    if oc.empty:
        c.info_empty("Nu există comenzi."); return
    oid = st.selectbox("Comandă", oc["id"].tolist())
    ln = d["lines"][d["lines"]["order_id"] == oid]
    p = capacity.pallets_per_line(ln, s)
    if p.empty:
        c.info_empty("Comanda nu are linii cu cantitate."); return
    miss = p[p["pallets"].isna()]["sku"].tolist()
    if miss:
        st.warning("Lipsesc dimensiuni/greutăți pentru: " + ", ".join(miss) + " – completează în liniile comenzii.")
    st.dataframe(p, hide_index=True, width="stretch", column_config={
        "sku": "SKU", "description": "Descriere", "qty": "Buc", "cartons": "Cartoane", "carton_kg": st.column_config.NumberColumn("kg/carton", format="%.1f"),
        "per_layer": "Cartoane/strat", "layers": "Straturi", "per_pallet": "Cartoane/palet", "pallets_vol": "Paleți (volum)", "pallets_wt": "Paleți (greutate)",
        "pallets": st.column_config.NumberColumn("PALEȚI FINALI", help="Maximul dintre volum și greutate; fiecare SKU are paleții lui (estimare conservatoare)."),
        "total_kg": st.column_config.NumberColumn("kg total", format="%.0f"), "volume_cm3": None})
    veh, tp, tkg, vol = capacity.vehicles(p, s)
    m = st.columns(3)
    m[0].metric("Paleți", f"{tp:,.0f}"); m[1].metric("Greutate (kg)", f"{tkg:,.0f}"); m[2].metric("Volum cartoane (m³)", f"{vol / 1e6:,.2f}")
    st.dataframe(veh, hide_index=True, width="stretch", column_config={
        "Utilizare paleti": st.column_config.ProgressColumn("Utilizare paleți", format="percent", min_value=0, max_value=1),
        "Utilizare greutate": st.column_config.ProgressColumn("Utilizare greutate", format="percent", min_value=0, max_value=1)})
    st.caption("Normele de paletizare și capacitățile se modifică în **Setări**. Compară rezultatul cu oferta transportatorului.")
