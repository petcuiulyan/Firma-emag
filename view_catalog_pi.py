"""Produse & PI: incarca PI de la furnizori (reguli sau AI), compara cu catalogul, actualizeaza produse, creeaza comanda."""
import io

import pandas as pd
import streamlit as st

import core_ai as ai
import core_bnr as bnr
import core_catalog as catalog
import core_pi_parser as pp
import core_schema as schema
import core_storage as storage
import view_common as c

LINE_COLS = ["sku", "description", "hs_code", "qty", "unit_price", "pcs_per_carton", "unit_weight_kg", "carton_l", "carton_w", "carton_h"]


def render():
    st.title("📦 Produse & PI furnizori")
    tab_pi, tab_cat, tab_hist = st.tabs(["⬆️ Încarcă PI", "📚 Catalog produse", "📈 Istoric prețuri"])
    d, s = c.load_all()
    with tab_pi:
        _upload(d, s)
    with tab_cat:
        st.caption("Catalogul e baza pentru comenzi, marjă și comparații. Editează direct în tabel; PI-urile îl completează automat.")
        edited = st.data_editor(d["catalog"], num_rows="dynamic", width="stretch", hide_index=True, key="cat_editor", column_config=c.column_config("catalog"))
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


def _api_key():
    try:
        k = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        k = ""
    return k or st.session_state.get("ai_key", "")


def _rules(f, raws):
    """Citire pe baza de reguli, cu potrivire de coloane editabila."""
    sheet = st.selectbox("Foaia", list(raws)) if len(raws) > 1 else next(iter(raws))
    raw = raws[sheet]
    h0, n0 = pp.detect_header(raw)
    a = st.columns(2)
    hdr = a[0].number_input("Rândul antetului (1 = primul rând)", 1, max(len(raw), 1), h0 + 1) - 1
    nh = a[1].radio("Rânduri de antet", [1, 2], index=n0 - 1, horizontal=True, help="PI-urile cu 'Order qty' deasupra 'Cartons / Pcs/ctns / Total pcs' au 2 rânduri.")
    df = pp.with_header(raw, hdr, nh)
    auto = pp.auto_map(list(df.columns))
    with st.expander("Potrivire coloane (detectată automat – verifică)", expanded=False):
        cols = ["(nu există)"] + list(df.columns)
        grid, mapping = st.columns(4), {}
        for i, (field, label) in enumerate(pp.FIELD_LABELS.items()):
            pick = grid[i % 4].selectbox(label, cols, index=cols.index(auto[field]) if field in auto else 0, key=f"map_{field}_{hdr}_{nh}")
            if pick != "(nu există)": mapping[field] = pick
    o = st.columns(3)
    wk = o[0].selectbox("Greutatea folosită", list(pp.WEIGHT_CHOICES), help="Pentru transport contează greutatea BRUTĂ (G.W.).")
    du = o[1].selectbox("Unitate dimensiuni carton", ["cm", "mm", "m"])
    one = o[2].checkbox("Dacă lipsește Buc/carton: presupun 1 carton per linie", help="Corect doar dacă fiecare linie e un singur carton (mostre).")
    field, basis = pp.WEIGHT_CHOICES[wk]
    return pp.normalize(df, mapping, field, basis, du, one), pp.detect_meta(raw)


def _ai(f, raws, key_slot):
    """Citire cu Claude; rezultatul se tine in session_state ca sa nu se apeleze API-ul la fiecare rerun."""
    ext = f.name.lower().rsplit(".", 1)[-1]
    key = _api_key()
    if not key:
        st.info("Pentru AI e nevoie de o cheie API Anthropic. Pe Streamlit Cloud: **Settings → Secrets** → `ANTHROPIC_API_KEY = \"sk-ant-...\"`. "
                "Temporar o poți introduce aici (rămâne doar în sesiune).")
        k = st.text_input("Cheie API Anthropic", type="password")
        if k: st.session_state["ai_key"] = k; st.rerun()
        return None, {}
    wk = st.radio("Greutatea folosită", ["Brută per carton (G.W.)", "Netă per carton (N.W.)"], horizontal=True)
    st.caption("🔒 Conținutul PI-ului se trimite către API-ul Anthropic. Datele bancare (beneficiar, SWIFT, IBAN) sunt eliminate din text înainte de trimitere; "
               "pentru PDF/imagini fișierul se trimite întreg.")
    slot = (f.name, f.size, wk)
    if st.button("🤖 Extrage liniile cu AI", type="primary"):
        with st.spinner("Claude citește PI-ul..."):
            try:
                model = st.secrets.get("ANTHROPIC_MODEL", ai.DEFAULT_MODEL) if hasattr(st, "secrets") else ai.DEFAULT_MODEL
            except Exception:
                model = ai.DEFAULT_MODEL
            try:
                meta, pi = ai.extract(f.name, f.getvalue(), raws if ext not in ai.MEDIA else {}, key, model, "gw" if wk.startswith("Brută") else "nw")
                st.session_state[key_slot] = (slot, pi, meta)
            except Exception as e:
                st.error(f"Extragerea a eșuat: {e}")
    got = st.session_state.get(key_slot)
    if got and got[0] == slot:
        return got[1], got[2]
    return None, {}


def _upload(d, s):
    f = st.file_uploader("Fișier PI (xlsx, xls, csv, pdf, png, jpg)", type=["xlsx", "xls", "csv", "pdf", "png", "jpg", "jpeg"])
    if not f:
        st.info("Încarcă o Proforma Invoice. Pentru Excel/CSV aplicația detectează antetul și coloanele (inclusiv antete pe 2 rânduri și celule unite). "
                "Pentru PDF/imagini, sau când formatul e neobișnuit, folosește varianta cu AI.")
        return
    is_doc = f.name.lower().endswith(("pdf", "png", "jpg", "jpeg"))
    raws = {} if is_doc else pp.read_raw(io.BytesIO(f.getvalue()) if not f.name.lower().endswith(".csv") else f)
    if is_doc:
        mode = "AI"
    else:
        mode = st.radio("Metodă de citire", ["Detectare automată (reguli)", "AI (Claude)"], horizontal=True)
    pi, meta = (_ai(f, raws, "ai_result") if mode.startswith("AI") or is_doc else _rules(f, raws))
    if pi is None:
        return
    if pi.empty:
        st.error("Nu am găsit linii valide (SKU + cantitate). Ajustează antetul/coloanele sau încearcă varianta AI."); return

    h = st.columns(4)
    supplier = h[0].text_input("Furnizor", value=meta.get("supplier", ""))
    pi_no = h[1].text_input("Nr. PI", value=meta.get("pi_no", ""))
    date = h[2].date_input("Data PI", value=meta.get("date", pd.Timestamp.today()))
    cur_opts = schema.CURRENCIES
    cur = h[3].selectbox("Moneda PI", cur_opts, index=cur_opts.index(meta["currency"]) if meta.get("currency") in cur_opts else 0)
    st.markdown("**Linii detectate** – verifică și completează ce lipsește (editabil):")
    pi = st.data_editor(pi[LINE_COLS], num_rows="dynamic", hide_index=True, width="stretch", key=f"pi_edit_{f.name}_{f.size}",
                        column_config=c.column_config("lines", hide=("order_id", "cbm_per_pc", "ro_price", "notes")))
    pi = schema.coerce("lines", pi.assign(order_id="")).drop(columns=["order_id", "cbm_per_pc", "ro_price", "notes"])
    pi = pi[pi["sku"].str.strip() != ""].reset_index(drop=True)
    miss = [f"{r['sku']}: " + ", ".join(n for n, k in (("buc/carton", "pcs_per_carton"), ("greutate", "unit_weight_kg"), ("dimensiuni", "carton_h")) if not r[k] or r[k] != r[k] or r[k] == 0)
            for _, r in pi.iterrows() if any(not r[k] or r[k] != r[k] for k in ("pcs_per_carton", "unit_weight_kg", "carton_h"))]
    if miss:
        st.warning("Date lipsă pentru transport/capacitate – " + "; ".join(miss))

    cmp = catalog.compare(pi, d["catalog"])
    icon = {"NOU": "🆕", "PRET SCHIMBAT": "💲", "DATE DIFERITE": "📐", "NESCHIMBAT": "✅"}
    cmp.insert(0, "Aplică", cmp["status"] != "NESCHIMBAT")
    cmp["status"] = cmp["status"].map(lambda x: f"{icon[x]} {x}")
    m = st.columns(4)
    for i, k in enumerate(icon):
        m[i].metric(k.title(), int(cmp["status"].str.contains(k).sum()))
    st.markdown("**Comparație PI vs catalog** (bifează ce se actualizează):")
    edited = st.data_editor(cmp, hide_index=True, width="stretch", key=f"pi_cmp_{f.name}_{f.size}", disabled=[x for x in cmp.columns if x != "Aplică"],
                            column_config={"delta_pct": st.column_config.NumberColumn("Δ preț", format="percent"), "prev_price": st.column_config.NumberColumn("Preț anterior")})
    sel = edited.loc[edited["Aplică"], "sku"].tolist()
    b = st.columns(2)
    if b[0].button(f"📚 Actualizează catalogul ({len(sel)} SKU)", disabled=not sel):
        cat, nn, nu = catalog.apply_to_catalog(pi, d["catalog"], supplier, cur, sel)
        storage.save("catalog", cat)
        storage.save("history", pd.concat([d["history"], catalog.history_rows(pi, supplier, pi_no, pd.Timestamp(date), cur)]))
        st.success(f"Catalog actualizat: {nn} produse noi, {nu} actualizate. Istoricul de prețuri a fost completat.")
    if b[1].button("🧾 Creează comandă (Draft) din acest PI", type="primary"):
        oid = catalog.next_order_id(d["orders"])
        fx = bnr.rate_for(pd.Timestamp(date))
        usd, eur = (fx[0], fx[1]) if fx else (s["usd_ron"], s["eur_ron"])
        row = {"id": oid, "date": pd.Timestamp(date), "supplier": supplier, "pi_no": pi_no, "goods_cur": cur, "usd_ron": usd, "eur_ron": eur,
               "transp_cur": cur, "incoterm": meta.get("incoterm", "DDP"), "transport_type": meta.get("transport_type", "Aerian"),
               "duty_pct": s["default_duty"], "vat_pct": s["vat_std"], "flat_fee_eur": 0.0, "status": "Draft"}
        storage.save("orders", pd.concat([d["orders"], pd.DataFrame([row])], ignore_index=True))
        storage.save("lines", pd.concat([d["lines"], catalog.lines_from_pi(pi, oid)], ignore_index=True))
        st.success(f"Comanda **{oid}** creată cu {len(pi)} linii. " + (f"Curs BNR din {fx[2]:%d.%m.%Y}: USD {fx[0]:.4f}, EUR {fx[1]:.4f}. " if fx else
                   "Cursul BNR nu s-a putut prelua – am pus cursul implicit din Setări. ") + "Completează tariful de transport în pagina **Comenzi**.")
