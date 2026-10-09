"""Curs oficial BNR dupa data. Citeste fisierele XML publice BNR (an intreg) si le tine in cache in data/.
Pentru zile fara curs (weekend / sarbatori) se foloseste ultima zi anterioara cu curs publicat."""
import datetime as dt
import time
import urllib.request
import xml.etree.ElementTree as ET

import core_storage as storage

URL_YEAR = "https://www.bnr.ro/files/xml/years/nbrfxrates{y}.xml"
CACHE_HOURS = 6  # pentru anul curent; anii trecuti nu se mai reiau


def parse_xml(content):
    """XML BNR -> {data: {moneda: curs RON pentru 1 unitate}}. Tine cont de atributul 'multiplier'."""
    out = {}
    for cube in ET.fromstring(content).iter():
        if cube.tag.endswith("Cube") and cube.get("date"):
            d = dt.date.fromisoformat(cube.get("date"))
            rates = {}
            for r in cube:
                if r.tag.endswith("Rate") and r.text:
                    rates[r.get("currency")] = float(r.text) / float(r.get("multiplier") or 1)
            out[d] = rates
    return out


def _year(y):
    path = storage.DATA_DIR / f"bnr_{y}.xml"
    fresh = path.exists() and (y < dt.date.today().year or time.time() - path.stat().st_mtime < CACHE_HOURS * 3600)
    if not fresh:
        try:
            req = urllib.request.Request(URL_YEAR.format(y=y), headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=10).read()
            storage.DATA_DIR.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except Exception:
            if not path.exists():
                return {}
    return parse_xml(path.read_bytes())


def rate_for(date):
    """(usd_ron, eur_ron, data_folosita) pentru data data sau None daca nu se poate prelua."""
    d0 = date.date() if hasattr(date, "date") else date
    for back in range(0, 12):
        d = d0 - dt.timedelta(days=back)
        r = _year(d.year).get(d)
        if r and "USD" in r and "EUR" in r:
            return r["USD"], r["EUR"], d
    return None
