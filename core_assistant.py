"""Context pentru asistentul AI: rezumat compact al datelor din aplicatie (setari, comenzi, produse, luni)."""
import core_margins as margins


def _f(x, n=2):
    return "-" if x is None or x != x else f"{x:,.{n}f}"


def build_context(d, s, oc, lc, months, max_chars=14000):
    out = [f"SETARI: curs implicit USD {s['usd_ron']}, EUR {s['eur_ron']}; TVA {s['vat_std']:.0%}; firma {'PLATITOARE' if s['vat_payer'] else 'NEPLATITOARE'} de TVA; "
           f"plafon TVA {s['vat_threshold']:,.0f} lei; impozit profit {s['profit_tax']:.0%}; micro {s['micro_tax']:.0%}; marja minima {s['min_margin']:.0%}."]
    out.append("COMENZI (id | data | furnizor | status | buc | marfa RON | transport RON | RON/kg | RON/CBM | total fara TVA | total cu TVA | avertismente):")
    for _, o in oc.sort_values("date").iterrows():
        dt = o["date"].strftime("%d.%m.%Y") if o["date"] == o["date"] else "-"
        out.append(f"{o['id']} | {dt} | {o['supplier']} | {o['status']} | {_f(o['qty_tot'], 0)} | {_f(o['goods_ron'])} | {_f(o['transp_ron'])} | "
                   f"{_f(o['ron_per_kg'])} | {_f(o['ron_per_cbm'])} | {_f(o['total_novat_ron'])} | {_f(o['total_vat_ron'])} | {o['warnings']}")
    base = margins.catalog_with_order_skus(d["catalog"], d["lines"])
    mt = margins.margin_table(base, margins.weighted_costs(lc, oc), s["min_margin"])
    out.append("PRODUSE (sku | descriere | importat | vandut | stoc | cost fara TVA | cost cu TVA | pret vanzare cu TVA | rata retur | marja TVA | marja non-TVA):")
    for _, r in mt.iterrows():
        out.append(f"{r['sku']} | {str(r['description'])[:40]} | {_f(r['qty'], 0)} | {_f(r['sold_qty'], 0)} | {_f(r['stock'], 0)} | {_f(r['cost_novat'])} | {_f(r['cost_vat'])} | "
                   f"{_f(r['sell_price_vat'])} | {_f(r['returns_pct'] * 100, 1)}% | {_f(r['margin_vat'] * 100, 1)}% | {_f(r['margin_nonvat'] * 100, 1)}%")
    if len(months):
        out.append("LUNI FISCALE (luna | inchisa | marfa | transport | taxe vamale | TVA import | alte costuri | OPEX | venit fara TVA | venit cu TVA | profit cash TVA | profit cash non-TVA):")
        for _, m in months.sort_values("month").iterrows():
            out.append(f"{m['month']} | {m['closed']} | {_f(m['goods_ron'])} | {_f(m['transport_ron'])} | {_f(m['duty_ron'])} | {_f(m['vat_ron'])} | {_f(m['local_ron'])} | "
                       f"{_f(m['opex_ron'])} | {_f(m['revenue_vat'])} | {_f(m['revenue_nonvat'])} | {_f(m['profit_cash_vat'])} | {_f(m['profit_cash_nonvat'])}")
    text = "\n".join(out)
    return text if len(text) <= max_chars else text[:max_chars] + "\n[...context trunchiat]"


SYSTEM = """Ești asistentul unei aplicații de calcul al costurilor de import (China → România) pentru o firmă mică (SRL) care vinde pe eMAG și pe site propriu.
Răspunde în română, concis și practic. Folosește DOAR datele din context pentru cifre; dacă o cifră lipsește, spune clar ce trebuie completat în aplicație.
Explică formulele când ești întrebat. Calculele fiscale sunt estimări de planificare, nu consultanță fiscală – recomandă confirmarea cu un contabil.
Valorile sunt în RON dacă nu scrie altfel. 'Cost fără TVA' se aplică firmei plătitoare de TVA (TVA import recuperabil), 'cost cu TVA' firmei neplătitoare.
"""
