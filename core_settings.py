"""Setari globale (echivalentul foii 'Setari si Plafoane')."""
DEFAULTS = {
    "usd_ron": 4.60, "eur_ron": 5.05,
    "vat_std": 0.21, "vat_reduced": 0.11, "vat_threshold": 395000.0,
    "profit_tax": 0.16, "micro_tax": 0.01, "micro_threshold_eur": 100000.0,
    "flat_fee_eur": 3.0, "logistics_lei": 25.0, "parcel_threshold_eur": 150.0,
    "default_duty": 0.0, "vat_payer": False,
    "pallet_l": 120.0, "pallet_w": 80.0, "pallet_empty_h": 15.0, "pallet_max_h": 220.0, "pallet_max_kg": 1000.0,
    "truck_pallets": 33, "truck_kg": 24000.0, "c20_pallets": 11, "c20_kg": 21700.0,
    "c40_pallets": 23, "c40_kg": 26000.0, "vol_divisor": 6000.0,
    "min_margin": 0.15,
    # taxa vamala pe cod NC/HS (fractie), ex. {"9503.00": 0.0}
    "hs_duties": {},
    # P&L: venituri lunare (fara TVA pentru varianta platitor / incasate pentru non-TVA)
    "revenue_vat": [0.0] * 12, "revenue_nonvat": [0.0] * 12,
    "opex": [
        ["Contabilitate SRL (outsourcing)", 150.0, 400.0], ["Cont bancar business", 0.0, 50.0],
        ["Abonament platforma site propriu", 100.0, 250.0], ["Depozitare marfa", 100.0, 400.0],
        ["Chirie spatiu / birou", 0.0, 1500.0], ["Mentenanta echipamente / IT / software", 50.0, 200.0],
        ["Marketing / Ads", 300.0, 900.0], ["Consumabile ambalare", 150.0, 350.0],
        ["Curierat suplimentar / retururi", 100.0, 250.0], ["Asigurari firma", 0.0, 150.0],
        ["Alte servicii", 0.0, 300.0],
    ],
}


def merged(saved):
    s = {**DEFAULTS, **(saved or {})}
    return s
