"""Extragere PI cu Claude (API Anthropic): xlsx/csv ca text, PDF si imagini direct. Optional - necesita cheie API.
Modelul intoarce JSON cu valorile BRUTE din document; conversiile (greutate/carton -> kg/buc) se fac aici, determinist."""
import base64
import json
import re
import urllib.error
import urllib.request

import numpy as np
import pandas as pd

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-5-5"
SENSITIVE = re.compile(r"beneficiary|swift|iban|account (name|number)|bank|routing", re.I)
MEDIA = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}

PROMPT = """Ești un asistent care extrage date dintr-o Proforma Invoice (PI) a unui furnizor din China pentru un importator român.
Returnează EXCLUSIV un obiect JSON valid (fără text în plus, fără ```), cu structura:
{"supplier": str|null, "pi_no": str|null, "date": "YYYY-MM-DD"|null, "currency": "USD"|"EUR"|"RON"|null,
 "incoterm": str|null, "freight": "Air"|"Sea"|"Road"|"Express"|null,
 "lines": [{"sku": str, "description": str|null, "hs_code": str|null, "qty": number (TOTAL bucăți comandate),
            "unit_price": number, "pcs_per_carton": number|null, "cartons": number|null,
            "carton_l_cm": number|null, "carton_w_cm": number|null, "carton_h_cm": number|null,
            "gross_weight_per_carton_kg": number|null, "net_weight_per_carton_kg": number|null, "notes": str|null}]}
Reguli: copiază valorile EXACT din document; dacă o valoare lipsește pune null – NU inventa și NU deduce.
Dimensiunile cartonului sunt cele ale CARTONULUI (nu ale produsului). Convertește dimensiunile în cm dacă sunt în alte unități.
Ignoră rândurile de total/subtotal, taxe, transport și datele bancare. O linie = un produs."""


def sheet_text(raw):
    """Foaie -> text compact pe randuri 'R18 | A=.. | C=..'; elimina celulele cu date bancare."""
    rows = []
    for r in range(len(raw)):
        cells = [f"{chr(65 + j) if j < 26 else 'C' + str(j)}={str(v).strip()}" for j, v in enumerate(raw.iloc[r])
                 if v is not None and not (isinstance(v, float) and np.isnan(v)) and str(v).strip() and not SENSITIVE.search(str(v))]
        if cells:
            rows.append(f"R{r + 1} | " + " | ".join(cells))
    return "\n".join(rows)


def build_body(file_name, file_bytes, sheets, model):
    ext = file_name.lower().rsplit(".", 1)[-1]
    if ext in MEDIA:
        kind = "document" if ext == "pdf" else "image"
        content = [{"type": kind, "source": {"type": "base64", "media_type": MEDIA[ext], "data": base64.b64encode(file_bytes).decode()}},
                   {"type": "text", "text": PROMPT}]
    else:
        text = "\n\n".join(f"=== Foaia {name} ===\n{sheet_text(df)}" for name, df in sheets.items())
        content = [{"type": "text", "text": f"{PROMPT}\n\nConținutul fișierului:\n{text[:60000]}"}]
    return {"model": model, "max_tokens": 8000, "messages": [{"role": "user", "content": content}]}


def call_api(body, key, timeout=180):
    req = urllib.request.Request(API_URL, data=json.dumps(body).encode(), method="POST",
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API Anthropic: {e.code} {e.read().decode()[:300]}") from e


def parse_response(resp, weight_field="gw"):
    """Raspuns API -> (meta, DataFrame linii standard). weight_field: 'gw' sau 'nw' (per carton)."""
    text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise RuntimeError("Răspunsul AI nu conține JSON.")
    data = json.loads(m.group(0))
    L = pd.DataFrame(data.get("lines") or [])
    for c in ("sku", "description", "hs_code", "qty", "unit_price", "pcs_per_carton", "cartons", "carton_l_cm", "carton_w_cm", "carton_h_cm",
              "gross_weight_per_carton_kg", "net_weight_per_carton_kg"):
        if c not in L: L[c] = np.nan
    num = lambda c: pd.to_numeric(L[c], errors="coerce")
    qty, ppc = num("qty"), num("pcs_per_carton").fillna(num("qty") / num("cartons").replace(0, np.nan))
    w = num("gross_weight_per_carton_kg" if weight_field == "gw" else "net_weight_per_carton_kg")
    out = pd.DataFrame({"sku": L["sku"].fillna("").astype(str).str.strip(), "description": L["description"].fillna("").astype(str),
                        "hs_code": L["hs_code"].fillna("").astype(str), "qty": qty, "unit_price": num("unit_price"), "pcs_per_carton": ppc,
                        "unit_weight_kg": w / ppc.replace(0, np.nan), "carton_l": num("carton_l_cm"), "carton_w": num("carton_w_cm"), "carton_h": num("carton_h_cm")})
    skip = (out["sku"] + " " + out["description"]).str.contains(r"total|subtotal|freight|shipping|insurance", case=False, regex=True)
    out = out[(out["qty"] > 0) & (out["sku"] != "") & ~skip].reset_index(drop=True)
    fr = {"Air": "Aerian", "Sea": "Maritim LCL", "Road": "Rutier", "Express": "Curier"}.get(data.get("freight"))
    meta = {"supplier": data.get("supplier"), "pi_no": data.get("pi_no"), "date": pd.to_datetime(data.get("date"), errors="coerce"),
            "currency": data.get("currency"), "incoterm": data.get("incoterm"), "transport_type": fr}
    return {k: v for k, v in meta.items() if v is not None and not (isinstance(v, float) and np.isnan(v)) and not pd.isna(v)}, out


def extract(file_name, file_bytes, sheets, key, model=DEFAULT_MODEL, weight_field="gw"):
    return parse_response(call_api(build_body(file_name, file_bytes, sheets, model), key), weight_field)
