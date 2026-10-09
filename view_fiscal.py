"""Fiscal: luna (costuri automate din comenzi + OPEX + inchidere), P&L anual, regimuri fiscale."""
import json

import pandas as pd
import plotly.express as px
import streamlit as st

import core_fiscal as fiscal
import core_margins as margins
import core_periods as periods
import core_schema as schema
import core_storage as storage
import view_common as c

N2 = lambda t: st.column_config.NumberColumn(t, format="%.2f")


def render():
    st.title("🏛️ Fiscal: luni, P&L și regim recomandat")
    d, s, oc, lc = c.compute_all()
    t1, t2, t3 = st.tabs(["📅 Lună: costuri + închidere", "📊 P&L pe luni", "⚖️ Regimuri fiscale"])
    with t1:
        _month_tab(d, s, oc, lc)
    with t2:
        _pl_tab(d["months"])
    with t3:
        _regimes_tab(d["months"], s)


def _month_tab(d, s, oc, lc):
    months = d["months"]
    closed = set(months.loc[months["closed"] == "Da", "month"])
    opts = periods.available_months(d["orders"], months)
    with_orders = set(d["orders"]["date"].dropna().dt.strftime("%Y-%m"))
    default = next((m for m in opts if m in with_orders and m not in closed), opts[-1])
    m = st.selectbox("Luna", opts, index=opts.index(default), format_func=lambda x: f"{x}  🔒 închisă" if x in closed else x)
    if m in closed:
        r = months[months["month"] == m].iloc[0]
        st.error(f"🔒 Luna {m} este închisă ({r['closed_at']:%d.%m.%Y}) și nu mai poate fi modificată: nici OPEX-ul, nici comenzile ei.")
        k = st.columns(6)
        for col, lab in zip(k, ["goods_ron", "transport_ron", "duty_ron", "vat_ron", "local_ron", "opex_ron"]):
            col.metric(schema.labels("months")[lab], f"{r[lab]:,.0f}")
        lab = schema.labels("months")
        rows = [(lab[k], f"{r[k]:,.2f}" if isinstance(r[k], float) else str(r[k])) for k in lab if k not in ("opex_detail", "sold_snapshot", "closed_at", "closed")]
        st.dataframe(pd.DataFrame(rows, columns=["Câmp", "Valoare"]), hide_index=True, width="stretch")
        st.caption("OPEX detaliat: " + ", ".join(f"{k} {v:,.0f}" for k, v in json.loads(r["opex_detail"] or "{}").items()))
        return
    last = periods.latest_closed(months)
    if last and m < last:
        st.error(f"Luna {m} e anterioară ultimei luni închise ({last}). Lunile se închid în ordine cronologică."); return
    inc = st.toggle("Include comenzile Draft", value=True, help="Comenzile noi sunt Draft până le schimbi statusul. Debifează dacă nu sunt încă plasate.")
    costs, om = periods.import_costs(oc, lc, m, inc)
    nodate = int(d["orders"]["date"].isna().sum())
    if nodate:
        st.warning(f"{nodate} comenzi nu au dată și nu intră în nicio lună – completează data în **Comenzi**.")
    st.markdown(f"**1 · Costuri de import din comenzile lunii {m}** (automat): " + (costs["orders"] or "nicio comandă"))
    k = st.columns(6)
    parts = [("Marfă (PI)", "goods_ron"), ("Transport", "transport_ron"), ("Taxe vamale", "duty_ron"), ("TVA import", "vat_ron"), ("Alte costuri (broker, transport intern)", "local_ron")]
    for col, (lab, key) in zip(k, parts):
        col.metric(lab, f"{costs[key]:,.0f} lei")
    k[5].metric("Total import", f"{sum(costs[x] for _, x in parts):,.0f} lei")
    bad = om[om["warnings"] != "OK"]
    if len(bad):
        st.warning("Comenzi cu avertismente: " + "; ".join(f"{r['id']}: {r['warnings']}" for _, r in bad.iterrows()))

    base = margins.catalog_with_order_skus(d["catalog"], d["lines"])
    mt = margins.margin_table(base, margins.weighted_costs(lc, oc), s["min_margin"])
    sales, sdf = periods.sales_in_month(mt, periods.snapshot_of(months))
    st.markdown("**2 · Vânzări din lună** (automat: *Vândut* din pagina Marjă − *Vândut* la ultima închidere)")
    if sdf.empty:
        st.info("Nicio vânzare înregistrată în lună. Actualizează coloana **Vândut** în pagina Marjă înainte de închidere.")
    else:
        st.dataframe(sdf[["sku", "description", "delta", "sell_price_vat", "valoare", "ok"]], hide_index=True, width="stretch", column_config={
            "sku": "SKU", "description": "Descriere", "delta": "Buc. vândute", "sell_price_vat": N2("Preț cu TVA"), "valoare": N2("Valoare"), "ok": "Preț și cost complete"})
        if (~sdf["ok"]).any():
            st.warning("Unele produse vândute nu au preț de vânzare sau cost – nu intră în venituri.")
    st.markdown("**3 · OPEX al lunii** (singurul lucru pe care îl introduci)")
    draft = months[months["month"] == m]
    if len(draft) and draft.iloc[0]["opex_detail"] not in ("", "{}"):
        opex0 = pd.DataFrame(list(json.loads(draft.iloc[0]["opex_detail"]).items()), columns=["Categorie", "Suma"])
    else:
        opex0 = pd.DataFrame([[r[0], (r[1] + r[2]) / 2] for r in s["opex"]], columns=["Categorie", "Suma"])
    opex = st.data_editor(opex0, num_rows="dynamic", hide_index=True, width="stretch", key=f"opex_{m}",
                          column_config={"Suma": st.column_config.NumberColumn("Sumă (lei)", format="%.2f")})
    st.caption("Ambalarea, depozitarea, livrarea și comisionul pe bucată sunt deja în costurile de vânzare din Marjă – nu le introduce și aici (ar fi dublate).")
    row = periods.build_row(m, costs, sales, opex.dropna(subset=["Categorie"]), mt)
    st.markdown("**4 · Rezultatul lunii**")
    r1 = st.columns(4)
    r1[0].metric("Venituri (fără TVA / cu TVA)", f"{row['revenue_vat']:,.0f} / {row['revenue_nonvat']:,.0f}")
    r1[1].metric("OPEX", f"{row['opex_ron']:,.0f} lei")
    r1[2].metric("Profit cash – plătitor / neplătitor", f"{row['profit_cash_vat']:,.0f} / {row['profit_cash_nonvat']:,.0f}")
    r1[3].metric("Profit contabil – plătitor / neplătitor", f"{row['profit_acc_vat']:,.0f} / {row['profit_acc_nonvat']:,.0f}")
    st.caption("**Cash** = venituri − toate costurile de import ale lunii − costuri de vânzare − OPEX (stocul cumpărat contează integral). "
               "**Contabil** = marja produselor vândute − OPEX (doar costul mărfii vândute). Pentru plătitor de TVA, TVA-ul de import nu e cost.")
    b = st.columns([1, 2])
    if b[0].button("💾 Salvează OPEX (luna rămâne deschisă)"):
        with c.guard():
            storage.save("months", pd.concat([months[months["month"] != m], schema.coerce("months", pd.DataFrame([row]))], ignore_index=True))
        st.toast("Salvat. Luna e încă deschisă.", icon="✅"); st.rerun()
    ok = b[1].checkbox(f"Înțeleg: după închidere, luna {m} (comenzi, linii, OPEX) nu se mai poate modifica", key=f"ok_{m}")
    if st.button(f"🔒 Salvează și închide luna {m}", type="primary", disabled=not ok):
        row = periods.build_row(m, costs, sales, opex.dropna(subset=["Categorie"]), mt, closed=True)
        with c.guard():
            storage.save("months", pd.concat([months[months["month"] != m], schema.coerce("months", pd.DataFrame([row]))], ignore_index=True))
        st.toast(f"Luna {m} a fost închisă.", icon="✅"); st.rerun()


def _pl_tab(months):
    if months.empty:
        c.info_empty("Nicio lună salvată încă. Salvează sau închide o lună în tabul anterior."); return
    basis = st.radio("Profit", ["Cash (cheltuielile lunii)", "Contabil (cost marfă vândută)"], horizontal=True)
    suf = "cash" if basis.startswith("Cash") else "acc"
    t = months.sort_values("month")
    show = t[["month", "closed", "revenue_vat", "revenue_nonvat", "goods_ron", "transport_ron", "duty_ron", "vat_ron", "local_ron", "opex_ron", f"profit_{suf}_vat", f"profit_{suf}_nonvat"]]
    st.dataframe(show, hide_index=True, width="stretch", column_config={**{k: N2(v) for k, v in schema.labels("months").items() if k.endswith("_ron") or k.startswith(("revenue", "profit"))},
                                                                      "month": "Lună", "closed": "Închisă"})
    g = t.melt(id_vars="month", value_vars=[f"profit_{suf}_vat", f"profit_{suf}_nonvat"], var_name="Variantă", value_name="Profit")
    g["Variantă"] = g["Variantă"].map({f"profit_{suf}_vat": "SRL plătitor TVA", f"profit_{suf}_nonvat": "SRL neplătitor"})
    st.plotly_chart(px.bar(g, x="month", y="Profit", color="Variantă", barmode="group", title="Profit pe lună (RON)"), width="stretch")


def _regimes_tab(months, s):
    basis = st.radio("Baza profitului pentru impozit", ["Cash (cheltuielile lunii)", "Contabil (cost marfă vândută)"], horizontal=True, key="rb",
                     help="Fiscal, stocul nevândut nu se deduce integral; varianta contabilă e mai apropiată de impozitarea reală.")
    project = st.toggle("Proiecție pe 12 luni (media lunilor închise × 12)", value=True)
    ca_v, pb_v, ca_n, pb_n, n = periods.annual(months, "cash" if basis.startswith("Cash") else "acc", project)
    if n == 0:
        c.info_empty("Comparația folosește lunile **închise**. Închide cel puțin o lună."); return
    st.caption(f"Pe baza a {n} luni închise" + (" (proiectat la 12 luni)." if project else "."))
    th = fiscal.thresholds(ca_v, ca_n, s)
    st.info(f"Plafon TVA ({s['vat_threshold']:,.0f} lei): {th['tva']}  \nPlafon micro (≈{th['micro_ron']:,.0f} lei): {th['micro']}")
    df, best = fiscal.compare(ca_v, pb_v, ca_n, pb_n, s)
    st.plotly_chart(px.bar(df[df["Scenariu"] == 0.0], x="Regim", y="Profit net", title="Profit net la prețul de bază"), width="stretch")
    pv = df.pivot(index="Regim", columns="Scenariu", values="Profit net")
    pv.columns = [f"{x:+.0%}" for x in pv.columns]
    st.dataframe(pv.style.format("{:,.0f}"), width="stretch")
    base = best[best["Scenariu"] == 0.0].iloc[0]
    st.success(f"Regim cu cel mai mare profit net (preț de bază): **{base['Regim']}** – {base['Profit net']:,.0f} lei")
    st.caption("Simulare de planificare, nu consultanță fiscală.")
