"""Produse & PI: incarca PI de la furnizori, compara cu catalogul, actualizeaza produse, creeaza comanda."""
import pandas as pd
import streamlit as st

import core_catalog as catalog
import core_pi_parser as pi_parser
import core_schema as schema
import core_storage as storage
import view_common as c


def render():
    st.title("📦 Produse & PI furnizori")
    tab_pi, tab_cat, tab_hist = st.tabs(["⬆️ Încarcă PI", "📚 Catalog produse", "📈 Istoric prețuri"])
    d, s = c.load_all()
    with tab_pi:
        _upload(d, s)
    with tab_cat:
        st.caption("Catalogul e baza pentru comenzi, marjă și comparații. Editează direct în tabel; PI-urile îl completează automat.")
        edited = st.data_editor(d["catalog"], num_rows="dynamic", width="stretch", hide_index=True, key="cat_editor",
                                column_config=c.column_config("catalog"))
        if st.button("💾 Salvează catalogul", type="primary"):
            storage.save("catalog", edited); st.success("Catalog salvat."); st.rerun()
    with tab_hist:
        h = d["history"].sort_values("date", ascending=False)
        if h.empty:
            c.info_empty("Istoricul se completează la fiecare PI importat.")
        else:
            sku = st.selectbox("SKU", ["(toate)"] + sorted(h["sku"].unique()))
            hv = h if sku == "(toate)" else h[h["sku"] == sku]
            st.dataframe(hv, hide_index=True, width="stretch", column_config=c.column_config("history"))
            if sku != "(toate)" and len(hv) > 1:
                st.line_chart(hv.sort_values("date").set_index("date")["unit_price"])


def _upload(d, s):
    f = st.file_uploader("Fișier PI (xlsx, xls sau csv)", type=["xlsx", "xls", "csv"])
    if not f:
        st.info("Încarcă o Proforma Invoice. Aplicația detectează automat antetul și coloanele; le poți corecta înainte de import.")
        return
    raws = pi_parser.read_raw(f)
    sheet = st.selectbox("Foaia", list(raws)) if len(raws) > 1 else next(iter(raws))
    raw = raws[sheet]
    hdr = st.number_input("Rândul antetului (1 = primul rând)", 1, max(len(raw), 1), pi_parser.detect_header(raw) + 1) - 1
    df = pi_parser.with_header(raw, hdr)
    cols = ["(nu există)"] + list(df.columns)
    auto = pi_parser.auto_map(list(df.columns))
    st.markdown("**Coloane** – verifică potrivirea automată:")
    grid = st.columns(5)
    mapping = {}
    for i, (field, label) in enumerate(pi_parser.FIELD_LABELS.items()):
        default = auto.get(field)
        pick = grid[i % 5].selectbox(label, cols, index=(default + 1) if default is not None else 0, key=f"map_{field}")
        if pick != "(nu există)": mapping[field] = pick
    o = st.columns(3)
    wb = o[0].selectbox("Greutatea din fișier este", ["per bucată", "per carton", "total linie"])
    du = o[1].selectbox("Unitate dimensiuni carton", ["cm", "mm", "m"])
    cur = o[2].selectbox("Moneda PI", schema.CURRENCIES)
    pi = pi_parser.normalize(df, mapping, {"per bucată": "per bucata"}.get(wb, wb), du)
    if pi.empty:
        st.error("Nu am găsit linii valide (SKU + cantitate). Verifică rândul antetului și potrivirea coloanelor."); return
    h = st.columns(3)
    supplier = h[0].text_input("Furnizor", value=_guess(raw, ("supplier", "seller", "from")))
    pi_no = h[1].text_input("Nr. PI", value=_guess(raw, ("pi no", "invoice no", "proforma")))
    date = h[2].date_input("Data PI", value=pd.Timestamp.today())
    cmp = catalog.compare(pi, d["catalog"])
    icon = {"NOU": "🆕", "PRET SCHIMBAT": "💲", "DATE DIFERITE": "📐", "NESCHIMBAT": "✅"}
    cmp.insert(0, "Aplică", cmp["status"] != "NESCHIMBAT")
    cmp["status"] = cmp["status"].map(lambda x: f"{icon[x]} {x}")
    m = st.columns(4)
    for i, k in enumerate(icon):
        m[i].metric(k.title(), int(cmp["status"].str.contains(k).sum()))
    st.markdown("**Comparație PI vs catalog** (bifează ce se actualizează):")
    edited = st.data_editor(cmp, hide_index=True, width="stretch", key="pi_cmp", disabled=[x for x in cmp.columns if x != "Aplică"],
                            column_config={"delta_pct": st.column_config.NumberColumn("Δ preț", format="percent"),
                                           "prev_price": st.column_config.NumberColumn("Preț anterior")})
    sel = edited.loc[edited["Aplică"], "sku"].tolist()
    b = st.columns(2)
    if b[0].button(f"📚 Actualizează catalogul ({len(sel)} SKU)", disabled=not sel):
        cat, nn, nu = catalog.apply_to_catalog(pi, d["catalog"], supplier, cur, sel)
        storage.save("catalog", cat)
        storage.save("history", pd.concat([d["history"], catalog.history_rows(pi, supplier, pi_no, pd.Timestamp(date), cur)]))
        st.success(f"Catalog actualizat: {nn} produse noi, {nu} actualizate. Istoricul de prețuri a fost completat.")
    if b[1].button("🧾 Creează comandă (Draft) din acest PI", type="primary"):
        oid = catalog.next_order_id(d["orders"])
        row = {"id": oid, "date": pd.Timestamp(date), "supplier": supplier, "pi_no": pi_no, "goods_cur": cur,
               "usd_ron": s["usd_ron"], "eur_ron": s["eur_ron"], "transp_cur": cur, "duty_pct": s["default_duty"], "vat_pct": s["vat_std"],
               "flat_fee_eur": 0.0, "status": "Draft"}
        storage.save("orders", pd.concat([d["orders"], pd.DataFrame([row])], ignore_index=True))
        storage.save("lines", pd.concat([d["lines"], catalog.lines_from_pi(pi, oid)], ignore_index=True))
        st.success(f"Comanda **{oid}** creată cu {len(pi)} linii. Completează cursul, data și transportul în pagina **Comenzi**.")


def _guess(raw, keys):
    """Cauta in primele randuri o eticheta de tip 'PI No: X' si returneaza valoarea de langa ea."""
    for i in range(min(12, len(raw))):
        row = [str(v) for v in raw.iloc[i] if str(v) != "nan"]
        for j, v in enumerate(row):
            vl = v.lower()
            if any(k in vl for k in keys):
                tail = vl.split(":", 1)[1].strip() if ":" in vl else ""
                if tail: return v.split(":", 1)[1].strip()
                if j + 1 < len(row): return row[j + 1]
    return ""
