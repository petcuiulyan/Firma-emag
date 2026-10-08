"""Setari globale, taxe vamale pe cod NC, backup / restore, import din Excel."""
import pandas as pd
import streamlit as st

import core_storage as storage
import view_common as c


def render():
    st.title("⚙️ Setări & Backup")
    d, s = c.load_all()
    t1, t2, t3 = st.tabs(["Setări globale", "Taxe vamale pe cod NC", "Backup & import"])
    with t1:
        with st.form("settings"):
            st.markdown("**Curs implicit** (se propune la comenzi noi; fiecare comandă își are propriul curs)")
            a = st.columns(2)
            s["usd_ron"] = a[0].number_input("USD→RON", value=s["usd_ron"], format="%.4f"); s["eur_ron"] = a[1].number_input("EUR→RON", value=s["eur_ron"], format="%.4f")
            st.markdown("**Fiscal**")
            b = st.columns(4)
            s["vat_std"] = b[0].number_input("TVA standard", value=s["vat_std"], format="%.2f"); s["vat_reduced"] = b[1].number_input("TVA redus", value=s["vat_reduced"], format="%.2f")
            s["vat_threshold"] = b[2].number_input("Plafon TVA (RON)", value=s["vat_threshold"]); s["micro_threshold_eur"] = b[3].number_input("Plafon micro (EUR)", value=s["micro_threshold_eur"])
            b = st.columns(4)
            s["profit_tax"] = b[0].number_input("Impozit profit", value=s["profit_tax"], format="%.2f"); s["micro_tax"] = b[1].number_input("Impozit micro", value=s["micro_tax"], format="%.3f")
            s["default_duty"] = b[2].number_input("Taxă vamală implicită", value=s["default_duty"], format="%.3f"); s["min_margin"] = b[3].number_input("Marjă minimă SKU", value=s["min_margin"], format="%.2f")
            s["vat_payer"] = st.toggle("Firma este plătitoare de TVA", value=s["vat_payer"])
            st.markdown("**Paletizare și transport**")
            p = st.columns(5)
            for i, (k, lab) in enumerate([("pallet_l", "Palet L (cm)"), ("pallet_w", "Palet l (cm)"), ("pallet_empty_h", "Înălț. palet gol"), ("pallet_max_h", "Înălț. max. stivuire"), ("pallet_max_kg", "Kg max/palet")]):
                s[k] = p[i].number_input(lab, value=float(s[k]))
            p = st.columns(6)
            for i, (k, lab) in enumerate([("truck_pallets", "Paleți/camion"), ("truck_kg", "Kg/camion"), ("c20_pallets", "Paleți/20'"), ("c20_kg", "Kg/20'"), ("c40_pallets", "Paleți/40'"), ("c40_kg", "Kg/40'")]):
                s[k] = p[i].number_input(lab, value=float(s[k]))
            s["vol_divisor"] = st.number_input("Divizor greutate volumetrică aerian (cm³/kg)", value=float(s["vol_divisor"]))
            if st.form_submit_button("💾 Salvează setările", type="primary"):
                storage.save_settings(s); st.success("Setări salvate.")
    with t2:
        st.caption("Taxa vamală diferă pe cod tarifar (NC/TARIC). Dacă un produs are cod NC aici, se folosește această taxă; altfel taxa comenzii.")
        hs = pd.DataFrame([{"Cod NC/HS": k, "Taxă vamală": v} for k, v in s["hs_duties"].items()], columns=["Cod NC/HS", "Taxă vamală"])
        ed = st.data_editor(hs, num_rows="dynamic", hide_index=True, column_config={"Taxă vamală": st.column_config.NumberColumn(format="percent")})
        if st.button("💾 Salvează taxele"):
            s["hs_duties"] = {str(r["Cod NC/HS"]).strip(): float(r["Taxă vamală"]) for _, r in ed.dropna().iterrows() if str(r["Cod NC/HS"]).strip()}
            storage.save_settings(s); st.success("Salvat.")
    with t3:
        st.warning("Pe Streamlit Community Cloud fișierele locale se pierd la repornire. Descarcă periodic backup-ul și restaurează-l după redeploy.")
        st.download_button("⬇️ Descarcă backup complet (xlsx)", storage.export_backup(), "backup_import_calculator.xlsx")
        f = st.file_uploader("Restaurează din backup (xlsx)", type="xlsx", key="restore")
        if f and st.button("♻️ Restaurează (înlocuiește datele curente)"):
            storage.restore_backup(f); st.success("Restaurat."); st.rerun()
        st.divider()
        st.markdown("**Importă din calculatorul Excel** (`Calculator_Cost_Import_Mostre.xlsx`: foile *Comenzi* și *PI Furnizor*)")
        g = st.file_uploader("Fișier Excel", type="xlsx", key="legacy")
        if g and st.button("📥 Importă comenzi și linii"):
            o, l = storage.import_legacy_excel(g)
            storage.save("orders", pd.concat([d["orders"][~d["orders"]["id"].isin(o["id"])], o], ignore_index=True))
            storage.save("lines", pd.concat([d["lines"][~d["lines"]["order_id"].isin(o["id"])], l], ignore_index=True))
            cat = d["catalog"].set_index("sku")
            new = l.drop_duplicates("sku").set_index("sku")[["description", "unit_weight_kg", "pcs_per_carton", "carton_l", "carton_w", "carton_h", "ro_price"]]
            new["last_price"] = l.drop_duplicates("sku", keep="last").set_index("sku")["unit_price"]
            storage.save("catalog", pd.concat([cat[~cat.index.isin(new.index)], new]).reset_index().rename(columns={"index": "sku"}))
            st.success(f"Importate {len(o)} comenzi, {len(l)} linii; catalogul a fost completat cu produsele din ele.")
