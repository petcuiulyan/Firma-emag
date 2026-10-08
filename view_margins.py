"""Marja per SKU: SRL platitor TVA vs neplatitor."""
import streamlit as st

import core_margins as margins
import core_storage as storage
import view_common as c


def render():
    st.title("📈 Marjă per produs")
    d, s, oc, lc = c.compute_all()
    st.caption("Costul vine automat din comenzile cu status **Plasată / În tranzit / Recepționată** (medie ponderată cu cantitatea). "
               "Parametrii de vânzare se editează aici și se salvează în catalog.")
    cat = d["catalog"][d["catalog"]["sku"] != ""]
    if cat.empty:
        c.info_empty("Catalogul e gol."); return
    sale = ["sku", "description", "sell_price_vat", "vat_pct", "commission_pct", "packaging", "courier", "storage", "returns_pct", "ads"]
    ed = st.data_editor(cat[sale], hide_index=True, width="stretch", key="mg_ed", disabled=["sku", "description"],
                        column_config=c.column_config("catalog"))
    if st.button("💾 Salvează parametrii de vânzare", type="primary"):
        full = d["catalog"].set_index("sku"); full.update(ed.set_index("sku")); storage.save("catalog", full.reset_index()); st.success("Salvat."); st.rerun()
    mt = margins.margin_table(cat.set_index("sku").drop(columns=sale[2:], errors="ignore").join(ed.set_index("sku")[sale[2:]]).reset_index(),
                              margins.weighted_costs(lc, oc), s["min_margin"])
    mv, mn = margins.portfolio(mt)
    m = st.columns(2)
    m[0].metric("Marjă medie portofoliu – SRL TVA", "–" if mv != mv else f"{mv:.1%}")
    m[1].metric("Marjă medie portofoliu – SRL non-TVA", "–" if mn != mn else f"{mn:.1%}")
    pc = lambda t: st.column_config.NumberColumn(t, format="percent")
    n2 = lambda t: st.column_config.NumberColumn(t, format="%.2f")
    st.dataframe(mt[["sku", "qty", "cost_novat", "cost_vat", "profit_vat", "margin_vat", "profit_nonvat", "margin_nonvat", "diff", "better", "below_min"]],
                 hide_index=True, width="stretch", column_config={
                     "sku": "SKU", "qty": "Cant. importată", "cost_novat": n2("Cost fără TVA"), "cost_vat": n2("Cost cu TVA"), "profit_vat": n2("Profit/buc TVA"),
                     "margin_vat": pc("Marjă TVA"), "profit_nonvat": n2("Profit/buc non-TVA"), "margin_nonvat": pc("Marjă non-TVA"), "diff": n2("Diferență"),
                     "better": "Mai profitabil ca", "below_min": f"Sub prag {s['min_margin']:.0%}?"})
    st.caption("Regula: nu lansa un SKU dacă marja netă e sub pragul minim din Setări în ambele variante.")
