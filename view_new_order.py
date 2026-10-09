"""Comanda noua: alege produse din catalog, cantitati (cartoane/paleti), vezi cost + capacitate, salveaza sau exporta."""
import math

import numpy as np
import pandas as pd
import streamlit as st

import core_capacity as capacity
import core_catalog as catalog
import core_costing as costing
import core_schema as schema
import core_storage as storage
import view_common as c
from view_order_form import order_form

LINE_VIEW = ["sku", "description", "qty", "unit_price", "unit_weight_kg", "pcs_per_carton", "carton_l", "carton_w", "carton_h", "hs_code"]


def render():
    st.title("🛒 Comandă nouă")
    d, s = c.load_all()
    cat = d["catalog"][d["catalog"]["sku"] != ""]
    if "no_lines" not in st.session_state:
        st.session_state["no_lines"] = schema.empty("lines")[LINE_VIEW]
    st.subheader("1 · Antet comandă")
    head = order_form({"id": catalog.next_order_id(d["orders"]), "supplier": ""}, s, "new")
    st.subheader("2 · Produse")
    if cat.empty:
        st.warning("Catalogul e gol – încarcă mai întâi un PI în **Produse & PI** sau adaugă produse manual mai jos.")
    sup = [x for x in cat["supplier"].unique() if x]
    f = st.columns([2, 3, 1])
    sup_f = f[0].selectbox("Filtru furnizor", ["(toți)"] + sup)
    pool = cat if sup_f == "(toți)" else cat[cat["supplier"] == sup_f]
    pick = f[1].multiselect("Adaugă din catalog", pool["sku"] + " – " + pool["description"].str[:40])
    if f[2].button("➕ Adaugă", width="stretch") and pick:
        rows = pool[pool["sku"].isin([p.split(" – ")[0] for p in pick])]
        add = pd.DataFrame({"sku": rows["sku"], "description": rows["description"], "qty": rows["pcs_per_carton"].fillna(0), "unit_price": rows["last_price"],
                            **{k: rows[k] for k in ("unit_weight_kg", "pcs_per_carton", "carton_l", "carton_w", "carton_h", "hs_code")}})
        st.session_state["no_lines"] = pd.concat([st.session_state["no_lines"], add], ignore_index=True); st.rerun()
    lines = st.data_editor(st.session_state["no_lines"], num_rows="dynamic", hide_index=True, width="stretch", key="no_editor",
                           column_config=c.column_config("lines", hide=("order_id", "cbm_per_pc", "ro_price", "notes")))
    r = st.columns(2)
    round_c = r[0].checkbox("Rotunjește cantitățile la cartoane întregi", value=True)
    r[1].caption("Cantitatea se rotunjește în sus la multiplu de buc/carton (comenzi bulk, cartoane/paleți întregi).")
    ln = schema.coerce("lines", lines.assign(order_id=head["id"]))
    ln = ln[ln["sku"].str.strip() != ""].copy()
    if round_c:
        ppc = ln["pcs_per_carton"].replace(0, np.nan)
        ln["qty"] = np.where(ppc.notna() & (ln["qty"] > 0), np.ceil(ln["qty"] / ppc) * ppc, ln["qty"])
    if ln.empty:
        return
    st.subheader("3 · Estimare cost și capacitate")
    oc, lc = costing.compute(schema.coerce("orders", pd.DataFrame([head])), ln, s)
    o = oc.iloc[0]
    m = st.columns(5)
    m[0].metric("Bucăți", f"{o['qty_tot']:,.0f}"); m[1].metric("Greutate (kg)", f"{o['w_tot']:,.1f}"); m[2].metric("Volum (CBM)", f"{o['v_tot']:,.2f}")
    m[3].metric("Marfă (RON)", f"{o['goods_ron']:,.0f}"); m[4].metric("Cost total cu TVA (RON)", f"{o['total_vat_ron']:,.0f}")
    if o["warnings"] != "OK":
        st.warning(o["warnings"])
    pal = capacity.pallets_per_line(ln, s)
    if not pal.empty:
        veh, tp, tkg, _ = capacity.vehicles(pal, s)
        st.caption(f"Paleți estimați: **{tp:,.0f}** · greutate totală: **{tkg:,.0f} kg**")
        st.dataframe(veh, hide_index=True, width="stretch", column_config={
            "Utilizare paleti": st.column_config.ProgressColumn("Utilizare paleți", format="percent", min_value=0, max_value=1),
            "Utilizare greutate": st.column_config.ProgressColumn("Utilizare greutate", format="percent", min_value=0, max_value=1)})
    show = lc[["sku", "description", "qty", "cost_novat_ron", "cost_vat_ron", "cost_vat_eur", "cost_vat_usd"]]
    st.dataframe(show, hide_index=True, width="stretch", column_config={
        "sku": "SKU", "description": "Descriere", "qty": "Cant.", "cost_novat_ron": st.column_config.NumberColumn("Fără TVA (RON)", format="%.2f"),
        "cost_vat_ron": st.column_config.NumberColumn("Cu TVA (RON)", format="%.2f"), "cost_vat_eur": st.column_config.NumberColumn("Cu TVA (EUR)", format="%.2f"),
        "cost_vat_usd": st.column_config.NumberColumn("Cu TVA (USD)", format="%.2f")})
    st.subheader("4 · Salvează")
    b = st.columns(3)
    exists = head["id"] in d["orders"]["id"].values
    if exists:
        st.error(f"ID-ul {head['id']} există deja – alege altul.")
    if b[0].button("💾 Salvează comanda", type="primary", disabled=exists or not head["id"]):
        with c.guard():
            storage.save("orders", pd.concat([d["orders"], schema.coerce("orders", pd.DataFrame([head]))], ignore_index=True))
            storage.save("lines", pd.concat([d["lines"], ln], ignore_index=True))
        st.session_state.pop("no_lines"); st.toast(f"Comanda {head['id']} salvată.", icon="✅"); st.rerun()
    po = ln[["sku", "description", "qty", "unit_price"]].assign(total=ln["qty"] * ln["unit_price"])
    b[1].download_button("📄 Descarcă comanda pentru furnizor (xlsx)", c.to_xlsx({"PO": po}), f"PO_{head['id']}.xlsx")
    if b[2].button("🗑️ Golește"):
        st.session_state.pop("no_lines", None); st.rerun()
