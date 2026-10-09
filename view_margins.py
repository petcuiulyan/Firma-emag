"""Marja per SKU (cu rata de retur si descompunere), cantitate importata si stoc estimat."""
import streamlit as st

import core_margins as margins
import core_schema as schema
import core_storage as storage
import view_common as c

SALE = ["sell_price_vat", "vat_pct", "commission_pct", "packaging", "courier", "storage", "returns_pct", "ads", "sold_qty"]


def render():
    st.title("📈 Marjă, cantitate importată și stoc")
    d, s, oc, lc = c.compute_all()
    inc_draft = st.toggle("Include comenzile Draft în costul mediu și cantități", value=True,
                          help="Comenzile noi sunt 'Draft' până le schimbi statusul în pagina Comenzi (Plasată / În tranzit / Recepționată).")
    statuses = None if inc_draft else [x for x in schema.STATUSES if x != "Draft"]
    n_draft = int((oc["status"] == "Draft").sum()) if len(oc) else 0
    if n_draft and not inc_draft:
        st.warning(f"{n_draft} comenzi sunt Draft și sunt excluse. Pornește comutatorul de mai sus sau schimbă statusul în **Comenzi**.")
    base = margins.catalog_with_order_skus(d["catalog"], d["lines"])
    if base.empty:
        c.info_empty("Nu există produse. Adaugă produse prin PI sau într-o comandă."); return

    st.caption("Completează **prețul de vânzare cu TVA** și costurile de vânzare; **Vândut** îl actualizezi manual (stoc = importat − vândut).")
    ed = st.data_editor(base[["sku", "description"] + SALE], hide_index=True, width="stretch", key="mg_ed", disabled=["sku", "description"],
                        column_config=c.column_config("catalog"))
    live = base.copy()
    live[SALE] = ed[SALE].values
    if st.button("💾 Salvează", type="primary"):
        storage.save("catalog", live); st.toast("Salvat în catalog.", icon="✅"); st.rerun()

    mt = margins.margin_table(live, margins.weighted_costs(lc, oc, statuses), s["min_margin"])
    mv, mn = margins.portfolio(mt)
    k = st.columns(4)
    k[0].metric("Bucăți importate", f"{mt['qty'].sum():,.0f}"); k[1].metric("Stoc estimat (buc)", f"{mt['stock'].sum():,.0f}")
    k[2].metric("Marjă portofoliu – SRL TVA", "–" if mv != mv else f"{mv:.1%}"); k[3].metric("Marjă portofoliu – non-TVA", "–" if mn != mn else f"{mn:.1%}")
    st.info("**Formula (neplătitor de TVA):** profit/buc = preț vânzare cu TVA − [achiziție + transport + taxă vamală + TVA import + broker/local] − ambalare − depozitare "
            "− livrare − ads − comision marketplace − **cost retur**.  \n"
            "**Cost retur** = rată retur × (cost + ambalare + depozitare + livrare + ads): presupune că unitățile returnate sunt pierdute (estimare prudentă; rata 0% = fără retururi).  \n"
            "**Plătitor de TVA:** prețul se împarte la (1 + TVA vânzare), iar TVA-ul de import nu e cost (se recuperează).")
    pc = lambda t: st.column_config.NumberColumn(t, format="percent")
    n2 = lambda t: st.column_config.NumberColumn(t, format="%.2f")
    n0 = lambda t: st.column_config.NumberColumn(t, format="%.0f")
    st.dataframe(mt[["sku", "description", "status", "qty", "qty_excl", "sold_qty", "stock", "cost_novat", "cost_vat", "sell_price_vat", "returns_pct", "returns_vat",
                     "returns_nonvat", "profit_vat", "margin_vat", "profit_nonvat", "margin_nonvat", "better", "below_min"]],
                 hide_index=True, width="stretch", column_config={
                     "sku": "SKU", "description": "Descriere", "status": "Stare calcul", "qty": n0("Importat (buc)"), "qty_excl": n0("Excluse (Draft)"),
                     "sold_qty": n0("Vândut"), "stock": n0("STOC estimat"), "cost_novat": n2("Cost fără TVA"), "cost_vat": n2("Cost cu TVA"),
                     "sell_price_vat": n2("Preț vânzare cu TVA"), "returns_pct": pc("Rată retur"), "returns_vat": n2("Cost retur/buc (TVA)"),
                     "returns_nonvat": n2("Cost retur/buc (non-TVA)"), "profit_vat": n2("Profit/buc TVA"), "margin_vat": pc("Marjă TVA"),
                     "profit_nonvat": n2("Profit/buc non-TVA"), "margin_nonvat": pc("Marjă non-TVA"), "better": "Mai profitabil ca",
                     "below_min": f"Sub prag {s['min_margin']:.0%}?"})
    with st.expander("🔎 Descompunerea costului pe bucată (RON) – de unde vine marja"):
        b = mt[["sku", "c_goods", "c_transport", "c_duty", "c_vat", "c_local", "packaging", "storage", "courier", "ads", "commission_amt", "returns_nonvat",
                "cost_vat", "sell_costs_nonvat", "sell_price_vat", "profit_nonvat"]].copy()
        b["total"] = b["cost_vat"] + b["sell_costs_nonvat"]
        st.dataframe(b.drop(columns=["cost_vat", "sell_costs_nonvat"]), hide_index=True, width="stretch", column_config={
            "sku": "SKU", "c_goods": n2("Achiziție"), "c_transport": n2("Transport"), "c_duty": n2("Taxă vamală"), "c_vat": n2("TVA import"), "c_local": n2("Broker/local"),
            "packaging": n2("Ambalare"), "storage": n2("Depozitare"), "courier": n2("Livrare"), "ads": n2("Ads"), "commission_amt": n2("Comision"),
            "returns_nonvat": n2("Retur"), "total": n2("TOTAL costuri"), "sell_price_vat": n2("Preț vânzare"), "profit_nonvat": n2("PROFIT/buc")})
        st.caption("Varianta neplătitor de TVA (toate costurile, inclusiv TVA import). Pentru plătitor: scazi coloana „TVA import” din total și împarți prețul la (1 + TVA).")
