"""Capacitate transport: cutii -> paleti -> camion / container / avion (foaia 'Capacitate Transport')."""
import math

import numpy as np
import pandas as pd


def _per_layer(l, w, pl, pw):
    if not (l > 0 and w > 0):
        return np.nan
    return max(int(pl // l) * int(pw // w), int(pl // w) * int(pw // l))


def pallets_per_line(lines, s):
    """Paleti necesari pe SKU (fiecare SKU are paletii lui - estimare conservatoare)."""
    rows = []
    for _, r in lines.iterrows():
        if not (r["qty"] > 0):
            continue
        ppc = r["pcs_per_carton"] if r["pcs_per_carton"] > 0 else np.nan
        cartons = math.ceil(r["qty"] / ppc) if ppc == ppc else np.nan
        carton_kg = r["unit_weight_kg"] * ppc if ppc == ppc else np.nan
        per_layer = _per_layer(r["carton_l"], r["carton_w"], s["pallet_l"], s["pallet_w"])
        layers = int((s["pallet_max_h"] - s["pallet_empty_h"]) // r["carton_h"]) if r["carton_h"] > 0 else np.nan
        per_pallet = per_layer * layers if per_layer == per_layer and layers == layers else np.nan
        by_vol = math.ceil(cartons / per_pallet) if cartons == cartons and per_pallet and per_pallet == per_pallet else np.nan
        total_kg = r["qty"] * r["unit_weight_kg"]
        by_wt = math.ceil(total_kg / s["pallet_max_kg"]) if total_kg > 0 else np.nan
        final = max([x for x in (by_vol, by_wt, 1) if x == x]) if (by_vol == by_vol or by_wt == by_wt) else np.nan
        rows.append({"sku": r["sku"], "description": r["description"], "qty": r["qty"], "cartons": cartons, "carton_kg": carton_kg,
                     "per_layer": per_layer, "layers": layers, "per_pallet": per_pallet, "pallets_vol": by_vol,
                     "pallets_wt": by_wt, "pallets": final, "total_kg": total_kg,
                     "volume_cm3": (r["carton_l"] * r["carton_w"] * r["carton_h"] * cartons) if cartons == cartons else np.nan})
    return pd.DataFrame(rows)


def vehicles(p, s):
    """Necesar pe mijloc de transport, pe baza totalurilor (paleti, kg, volum)."""
    pal = float(p["pallets"].sum(skipna=True)) if len(p) else 0.0
    kg = float(p["total_kg"].sum(skipna=True)) if len(p) else 0.0
    vol = float(p["volume_cm3"].sum(skipna=True)) if len(p) else 0.0
    out = []
    for name, np_, kgcap in (("Camion complet (prelata 13.6 m)", s["truck_pallets"], s["truck_kg"]),
                             ("Container 20'", s["c20_pallets"], s["c20_kg"]), ("Container 40'", s["c40_pallets"], s["c40_kg"])):
        n = max(math.ceil(pal / np_), math.ceil(kg / kgcap), 1 if pal else 0)
        out.append({"Mijloc": name, "Unitati necesare": n, "Utilizare paleti": pal / (n * np_) if n else np.nan,
                    "Utilizare greutate": kg / (n * kgcap) if n else np.nan})
    vw = vol / s["vol_divisor"]
    out.append({"Mijloc": "Aerian (greutate taxabila kg)", "Unitati necesare": max(kg, vw), "Utilizare paleti": np.nan,
                "Utilizare greutate": np.nan})
    return pd.DataFrame(out), pal, kg, vol
