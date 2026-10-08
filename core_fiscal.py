"""P&L lunar-anual si comparatia celor 4 regimuri fiscale x 5 scenarii de pret."""
import numpy as np
import pandas as pd

MONTHS = ["Ian", "Feb", "Mar", "Apr", "Mai", "Iun", "Iul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SCENARIOS = [-0.05, -0.02, 0.0, 0.02, 0.05]
REGIMES = ["SRL TVA + Micro 1%", "SRL TVA + Profit 16%", "SRL non-TVA + Micro 1%", "SRL non-TVA + Profit 16%"]


def opex_monthly(opex_rows):
    """OPEX lunar folosit in P&L = media dintre estimarea minima si maxima."""
    return float(sum((r[1] + r[2]) / 2 for r in opex_rows))


def monthly_pl(revenue, margin, opex):
    rev = np.array(revenue, dtype=float)
    gross = rev * (0.0 if margin != margin else margin)
    return pd.DataFrame({"Luna": MONTHS, "Venit": rev, "Profit din vanzari": gross, "OPEX": opex, "Profit brut": gross - opex})


def compare(ca_vat, pb_vat, ca_non, pb_non, s):
    """Profit net pe regim si scenariu. Impozit micro = % din CA; profit = % din max(profit brut, 0)."""
    rows = []
    for name, ca, pb, micro in ((REGIMES[0], ca_vat, pb_vat, True), (REGIMES[1], ca_vat, pb_vat, False),
                                (REGIMES[2], ca_non, pb_non, True), (REGIMES[3], ca_non, pb_non, False)):
        for sc in SCENARIOS:
            c, p = ca * (1 + sc), pb + ca * sc
            tax = c * s["micro_tax"] if micro else max(p, 0) * s["profit_tax"]
            rows.append({"Regim": name, "Scenariu": sc, "Cifra afaceri": c, "Profit brut": p, "Impozit": tax, "Profit net": p - tax,
                         "Marja neta": (p - tax) / c if c else np.nan})
    df = pd.DataFrame(rows)
    best = df.loc[df.groupby("Scenariu")["Profit net"].idxmax()][["Scenariu", "Regim", "Profit net"]]
    return df, best


def thresholds(ca_vat, ca_non, s):
    ca = max(ca_vat, ca_non)
    micro_ron = s["micro_threshold_eur"] * s["eur_ron"]
    return {"tva": ("ATENTIE: peste plafon - inregistrare TVA OBLIGATORIE" if ca > s["vat_threshold"] else "OK - sub plafon, TVA optionala"),
            "micro": ("ATENTIE: peste plafon micro - doar impozit pe profit" if ca > micro_ron else "OK - sub plafon micro"),
            "ca": ca, "micro_ron": micro_ron}
