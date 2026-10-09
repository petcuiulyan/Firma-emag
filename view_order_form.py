"""Formular antet comanda (reutilizat de 'Comanda noua' si 'Comenzi')."""
import pandas as pd
import streamlit as st

import core_bnr as bnr

import core_schema as schema


def _fill_bnr(k):
    """Callback: pune cursul BNR din data comenzii in campurile USD / EUR."""
    r = bnr.rate_for(st.session_state[k("date")])
    if r:
        st.session_state[k("usd")], st.session_state[k("eur")] = round(r[0], 4), round(r[1], 4)
        st.session_state[k("bnr_msg")] = f"Curs BNR din {r[2]:%d.%m.%Y}: USD {r[0]:.4f} · EUR {r[1]:.4f}"
    else:
        st.session_state[k("bnr_msg")] = "Nu am putut prelua cursul BNR (fără internet sau dată viitoare). Introdu-l manual."


def order_form(v, s, key, id_locked=False):
    """v: dict cu valorile curente. Returneaza dict cu valorile din widgeturi."""
    k = lambda n: f"{key}_{n}"
    nz = lambda x, d: d if x is None or x != x else x
    out = {}
    a = st.columns(5)
    out["id"] = a[0].text_input("ID comandă", v.get("id", ""), key=k("id"), disabled=id_locked)
    dt = v.get("date")
    out["date"] = pd.Timestamp(a[1].date_input("Data comenzii", value=(pd.Timestamp.today() if dt is None or pd.isna(dt) else dt), key=k("date")))
    out["supplier"] = a[2].text_input("Furnizor", v.get("supplier", ""), key=k("sup"))
    out["pi_no"] = a[3].text_input("Nr. PI", v.get("pi_no", ""), key=k("pi"))
    out["status"] = a[4].selectbox("Status", schema.STATUSES, schema.STATUSES.index(v.get("status", "Draft")), key=k("st"))
    b = st.columns(5)
    out["goods_cur"] = b[0].selectbox("Moneda marfă", schema.CURRENCIES, schema.CURRENCIES.index(v.get("goods_cur", "USD")), key=k("gc"))
    out["usd_ron"] = b[1].number_input("Curs USD→RON", format="%.4f", key=k("usd"), **({} if k("usd") in st.session_state else {"value": float(nz(v.get("usd_ron"), s["usd_ron"]))}))
    out["eur_ron"] = b[2].number_input("Curs EUR→RON", format="%.4f", key=k("eur"), **({} if k("eur") in st.session_state else {"value": float(nz(v.get("eur_ron"), s["eur_ron"]))}))
    out["incoterm"] = b[3].text_input("Incoterm", v.get("incoterm", "DDP"), key=k("inc"))
    out["alloc_method"] = b[4].selectbox("Alocare transport pe produs", schema.METHODS, schema.METHODS.index(v.get("alloc_method", "Automat")), key=k("am"),
                                         help="Automat = după baza tarifului: kg → greutate, CBM → volum.")
    st.button("🏦 Preia cursul BNR din data comenzii", key=k("bnr"), on_click=_fill_bnr, args=(k,),
              help="Folosește cursul oficial BNR din ziua selectată (sau ultima zi lucrătoare dinainte).")
    if st.session_state.get(k("bnr_msg")):
        st.caption(st.session_state[k("bnr_msg")])
    t = st.columns(5)
    out["transport_type"] = t[0].selectbox("Tip transport", schema.TRANSPORT_TYPES, schema.TRANSPORT_TYPES.index(v.get("transport_type", "Aerian")), key=k("tt"))
    out["transp_cur"] = t[1].selectbox("Moneda transport", schema.CURRENCIES, schema.CURRENCIES.index(v.get("transp_cur", "USD")), key=k("tc"))
    out["transp_basis"] = t[2].selectbox("Tarif pe", schema.BASES, schema.BASES.index(v.get("transp_basis", "Total fix")), key=k("tb"),
                                         help="kg = preț/kg · CBM = preț/m³ · Total fix = suma totală a transportului")
    out["transp_rate"] = t[3].number_input("Tarif transport", value=float(nz(v.get("transp_rate"), 0.0)), min_value=0.0, key=k("tr"))
    out["min_chargeable"] = t[4].number_input("Minim taxabil (kg/CBM)", value=float(nz(v.get("min_chargeable"), 0.0)), min_value=0.0, key=k("mc"))
    u = st.columns(5)
    out["volumetric"] = u[0].selectbox("Greutate volumetrică?", ["Nu", "Da"], 1 if v.get("volumetric") == "Da" else 0, key=k("vo"),
                                       help="Aerian cu tarif pe kg: se taxează maximul dintre greutatea reală și cea volumetrică.")
    out["insurance"] = u[1].number_input("Asigurare + alte (moneda transport)", value=float(nz(v.get("insurance"), 0.0)), min_value=0.0, key=k("ins"))
    out["local_ron"] = u[2].number_input("Broker / transport intern (RON)", value=float(nz(v.get("local_ron"), 0.0)), min_value=0.0, key=k("loc"),
                                         help="Nu intră în baza TVA.")
    out["duty_pct"] = u[3].number_input("Taxă vamală %", value=100 * float(nz(v.get("duty_pct"), s["default_duty"])), min_value=0.0, key=k("du")) / 100
    out["vat_pct"] = u[4].number_input("TVA import %", value=100 * float(nz(v.get("vat_pct"), s["vat_std"])), min_value=0.0, key=k("vat")) / 100
    with st.expander("Colete mici (taxă forfetară UE / taxă logistică RO) – de regulă 0 la comenzi pe paleți"):
        e = st.columns(4)
        out["n_categories"] = e[0].number_input("Nr. categorii", value=float(nz(v.get("n_categories"), 0)), min_value=0.0, key=k("nc"))
        out["flat_fee_eur"] = e[1].number_input("Taxă forfetară EUR/categ.", value=float(nz(v.get("flat_fee_eur"), 0.0)), min_value=0.0, key=k("ff"))
        out["n_parcels"] = e[2].number_input("Nr. colete", value=float(nz(v.get("n_parcels"), 1)), min_value=0.0, key=k("np"))
        out["logistics_lei"] = e[3].number_input("Taxă logistică RO lei/colet", value=float(nz(v.get("logistics_lei"), 0.0)), min_value=0.0, key=k("ll"))
    out["notes"] = v.get("notes", "")
    return out
