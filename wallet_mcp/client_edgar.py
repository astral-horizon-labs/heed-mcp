"""Ce que la société publie : dates de résultats, dépôts récents, chiffres déclarés.

POURQUOI (2026-11-22, lot 5 du plan grand public). Tradewind lit le prix. Le prix ne
contient pas le trou d'une publication : un titre qui « tient » le jeudi peut ouvrir
dix pour cent plus bas le vendredi de ses résultats. La maquette validée laissait donc
un trou assumé, « la prochaine date de résultats s'ajoutera ici ». Ce module le
comble, et donne à l'assistant de quoi répondre au reste sans inventer : ce que la
société a déposé récemment, et ses chiffres tels qu'elle les déclare.

LA SOURCE est EDGAR, la base publique de la SEC, lue depuis la machine du client : rien
ne passe par notre serveur, aucune clé. La SEC exige un User-Agent avec un contact ;
c'est celui du studio. Une société qui ne dépose rien à la SEC (cotation étrangère,
fonds) se dit telle, elle ne se devine pas.

CE QUI EST MESURÉ ET CE QUI EST ESTIMÉ, dit dans chaque résultat :
  - les dates PASSÉES de résultats sont celles des 8-K portant l'item 2.02 : mesurées ;
  - la PROCHAINE date est une estimation tirée du rythme de la société (la publication
    du même trimestre un an plus tôt). Aucune société ne la dépose à l'avance : elle
    porte sa fenêtre et le mot « estimée », jamais une date ferme ;
  - le mouvement « à la publication » est celui de la SEMAINE qui la contient, sur nos
    clôtures hebdomadaires. Il mêle la publication au reste de la semaine : c'est une
    borne d'amplitude, pas la réaction du jour. Mesuré sur 397 titres le 2026-10-29 :
    l'amplitude d'une réaction se répète, son sens ne se prédit pas. Le résultat ne
    donne donc jamais de sens attendu.
"""
from __future__ import annotations

import bisect
import datetime
import json
import os
import pathlib
import statistics
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
for folder in (ROOT / "scripts", pathlib.Path(__file__).resolve().parent):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import atomic_file  # noqa: E402  # type: ignore[import-not-found]
import client_book  # noqa: E402
import client_market  # noqa: E402

SEC_UA = {"User-Agent": "Tradewind (Astral Horizon Labs) hello@astral-horizon-labs.com"}
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
DOCUMENT_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
#: Un dépôt se relit au plus deux fois par jour ; la table des tickers, une fois par semaine.
MAX_AGE_S = 12 * 3600
TICKERS_MAX_AGE_S = 7 * 24 * 3600
RESULTS_ITEM = "2.02"
#: Une publication à moins de cinq séances : la semaine qui vient.
SOON_DAYS = 7
WINDOW_DAYS = 7
RECENT_DAYS = 120
ITEMS = {
    "1.01": "a material agreement signed", "1.02": "a material agreement ended", "1.03": "bankruptcy or receivership",
    "2.01": "an acquisition or a disposal completed", "2.02": "results published", "2.05": "a restructuring",
    "2.06": "an impairment", "3.01": "a delisting notice", "3.02": "shares sold privately",
    "4.02": "earlier financial statements can no longer be relied on", "5.02": "a director or officer change",
    "5.07": "a shareholder vote", "7.01": "a disclosure to investors", "8.01": "another event the company chose to report",
}
FORMS = {"10-K": "annual report", "10-Q": "quarterly report", "8-K": "event report", "S-1": "securities registration",
         "S-3": "securities registration", "424B5": "prospectus for an offering of securities (shares or debt)", "20-F": "annual report (foreign filer)",
         "6-K": "report of a foreign filer"}
REVENUE_TAGS = ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet",
                "RevenueFromContractWithCustomerIncludingAssessedTax")
INCOME_TAG = "NetIncomeLoss"
NOT_A_FILER = ("{symbol} files nothing with the SEC under that symbol (a foreign listing, a fund, or another "
               "ticker): no publication date or declared figure can be read")


def folder() -> pathlib.Path:
    return client_book.state_dir() / "edgar"


def fetch(name: str, url: str, max_age_s: int, opener, now: datetime.datetime) -> tuple[dict | None, str | None]:
    """(document, erreur) : la copie gardée si elle est fraîche, sinon EDGAR ; en panne,
    la copie gardée sert encore et la panne se dit."""
    path = folder() / name
    fresh = path.exists() and now.timestamp() - path.stat().st_mtime < max_age_s
    error = None
    if not fresh:
        try:
            with opener(urllib.request.Request(url, headers=SEC_UA), timeout=30) as response:
                payload = response.read().decode("utf-8")
            json.loads(payload)
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_file.write_text(path, payload)
            os.utime(path, (now.timestamp(), now.timestamp()))
        except urllib.error.HTTPError as failure:
            error = f"the SEC answered {failure.code}"
        except (urllib.error.URLError, TimeoutError, OSError):
            error = "the SEC could not be reached"
        except ValueError:
            error = "the SEC returned an unreadable document"
    if not path.exists():
        return None, error or "nothing kept"
    try:
        return json.loads(path.read_text(encoding="utf-8")), error
    except ValueError:
        return None, "the kept copy is unreadable"


def company(symbol: str, opener, now: datetime.datetime) -> tuple[dict | None, str | None]:
    """({cik, name, symbol}, erreur) : la société derrière un symbole, selon la table de la SEC."""
    table, error = fetch("company_tickers.json", TICKERS_URL, TICKERS_MAX_AGE_S, opener, now)
    if table is None:
        return None, f"the SEC company list is unavailable: {error}"
    wanted = symbol.strip().upper().replace(" ", "-").replace(".", "-")
    for row in table.values():
        if str(row.get("ticker", "")).upper() == wanted:
            return {"cik": int(row["cik_str"]), "name": row.get("title"), "symbol": wanted}, None
    return None, NOT_A_FILER.format(symbol=wanted)


def recent_filings(found: dict, opener, now: datetime.datetime) -> tuple[list[dict], str | None]:
    """Les dépôts récents de la société, du plus récent au plus ancien."""
    data, error = fetch(f"submissions-{found['cik']}.json", SUBMISSIONS_URL.format(cik=found["cik"]),
                        MAX_AGE_S, opener, now)
    if data is None:
        return [], f"the company's filings are unavailable: {error}"
    recent = (data.get("filings") or {}).get("recent") or {}
    rows = []
    for index, form in enumerate(recent.get("form") or []):
        def cell(key: str, position: int = index) -> str:
            values = recent.get(key) or []
            return str(values[position]) if position < len(values) else ""
        rows.append({"form": form, "date": cell("filingDate"), "items": [item.strip() for item in cell("items").split(",")
                                                                           if item.strip()],
                     "accession": cell("accessionNumber"), "document": cell("primaryDocument")})
    return rows, error


def results_dates(rows: list[dict]) -> list[datetime.date]:
    """Les dates où la société a publié ses résultats : ses 8-K portant l'item 2.02."""
    dates = set()
    for row in rows:
        if row["form"] == "8-K" and RESULTS_ITEM in row["items"]:
            try:
                dates.add(datetime.date.fromisoformat(row["date"]))
            except ValueError:
                continue
    return sorted(dates)


def expected_next(dates: list[datetime.date], today: datetime.date) -> dict | None:
    """La prochaine publication, ESTIMÉE sur le rythme de la société : celle du même
    trimestre un an plus tôt, ou à défaut l'écart médian entre ses publications."""
    if len(dates) < 2:
        return None
    if len(dates) >= 4:
        around, basis = dates[-4] + datetime.timedelta(days=364), "the release of the same quarter a year earlier"
    else:
        gaps = [(later - earlier).days for earlier, later in zip(dates, dates[1:])]
        around, basis = dates[-1] + datetime.timedelta(days=round(statistics.median(gaps))), \
            "the median gap between its past releases"
    days = (around - today).days
    return {"around": around.isoformat(),
            "window": [(around - datetime.timedelta(days=WINDOW_DAYS)).isoformat(),
                       (around + datetime.timedelta(days=WINDOW_DAYS)).isoformat()],
            "days_until": days, "within_a_week": -WINDOW_DAYS <= days <= SOON_DAYS,
            "overdue": days < -WINDOW_DAYS,
            "estimated_from": basis,
            "certainty": "estimated, not announced: the company does not file its date in advance"}


def week_moves(dates: list[datetime.date], closes: dict[str, float]) -> list[dict]:
    """Le mouvement de la semaine de chaque publication, sur les clôtures hebdomadaires.

    Une semaine se date par son premier jour de Bourse, qui n'est pas toujours un
    lundi : la semaine d'un lundi férié est datée du mardi. Constaté le 2026-11-22 sur
    la publication de Procter & Gamble du 22/01/2026, perdue par une recherche du lundi.
    """
    weeks = sorted(closes)
    stamps = [datetime.date.fromisoformat(week) for week in weeks]
    moves = []
    for date in dates:
        position = bisect.bisect_right(stamps, date) - 1
        if position < 1 or (date - stamps[position]).days > 6:
            continue
        before = closes[weeks[position - 1]]
        moves.append({"published": date.isoformat(),
                      "week_pct": round((closes[weeks[position]] / before - 1) * 100, 2)})
    return moves


def upcoming(getter=None, *, opener=urllib.request.urlopen, now: datetime.datetime | None = None,
             days: int = 14) -> dict:
    """Les lignes du livre dont la publication est attendue dans les `days` jours."""
    import client_plans
    import client_risk

    now = now or client_book.now_utc()
    found, error = client_risk.context(now)
    if error:
        return {"error": error}
    soon, unknown = [], []
    for position in found["snapshot"]["positions"]:
        symbol = client_plans.ticker(position)
        read = earnings(symbol, getter, opener=opener, now=now)
        expected = None if "error" in read else read["next_release"]
        if expected is None:
            unknown.append(symbol)
            continue
        if -WINDOW_DAYS <= expected["days_until"] <= days:
            weeks = read.get("release_weeks") or {}
            soon.append({"symbol": symbol, "around": expected["around"], "window": expected["window"],
                         "days_until": expected["days_until"], "last_release": read["last_release"],
                         "median_move_in_a_release_week_pct": weeks.get("median_move_pct"),
                         "largest_fall_in_a_release_week_pct": weeks.get("largest_fall_pct"),
                         "weight_pct": found["rows"][position["contract_description"]].get("weight_value_pct")})
    soon.sort(key=lambda row: row["days_until"])
    return {"report_date": found["snapshot"]["date"], "within_days": days, "expected_soon": soon,
            "no_date_for": sorted(unknown),
            "certainty": "every date is estimated from the company's own rhythm, not announced: give the window",
            "reading": ("a release is the one thing the chart does not hold: say which holdings report soon "
                        "and how much their release weeks have moved, never which way")}


def earnings(symbol: str, getter=None, *, opener=urllib.request.urlopen,
             now: datetime.datetime | None = None) -> dict:
    """Quand la société publie, et ce que ses publications ont fait au cours."""
    now = now or client_book.now_utc()
    found, error = company(symbol, opener, now)
    if found is None:
        return {"error": error}
    rows, stale = recent_filings(found, opener, now)
    if not rows:
        return {"error": stale}
    dates = results_dates(rows)
    out = {"symbol": found["symbol"], "company": found["name"],
           "past_releases": [date.isoformat() for date in dates[-8:]],
           "last_release": dates[-1].isoformat() if dates else None,
           "next_release": expected_next(dates, now.date()),
           "notes": [f"today's read failed, showing the copy kept earlier: {stale}"] if stale else []}
    if not dates:
        out["notes"].append("no results release found in its recent filings: a recent listing, or a filer "
                            "that reports results another way")
    target = client_market.resolve(symbol, client_market.held_positions(now))
    closes = {}
    if target is not None:
        if getter is None:
            getter, _ = client_market.getter_or_error()
        if getter is not None:
            closes, _, _ = client_market.weekly_closes(target["conid"], getter, now)
    moves = week_moves(dates, closes)
    if moves:
        sizes = sorted(abs(move["week_pct"]) for move in moves)
        out["release_weeks"] = {
            "count": len(moves), "median_move_pct": round(statistics.median(sizes), 2),
            "largest_fall_pct": min(move["week_pct"] for move in moves),
            "largest_rise_pct": max(move["week_pct"] for move in moves),
            "last_four": moves[-4:],
            "reading": ("the move of the WEEK holding each release, not of the day: a bound on size. The size "
                        "of a reaction tends to repeat, its direction does not: never say which way the next "
                        "one will go"),
        }
    else:
        out["notes"].append("no weekly prices on our server for the weeks of its releases: no size to give")
    return out


def filings(symbol: str, *, opener=urllib.request.urlopen, now: datetime.datetime | None = None) -> dict:
    """Ce que la société a déposé ces quatre derniers mois, en mots simples, avec le lien."""
    now = now or client_book.now_utc()
    found, error = company(symbol, opener, now)
    if found is None:
        return {"error": error}
    rows, stale = recent_filings(found, opener, now)
    if not rows:
        return {"error": stale}
    since = (now.date() - datetime.timedelta(days=RECENT_DAYS)).isoformat()
    listed = []
    for row in rows:
        if row["date"] < since or row["form"] not in FORMS:
            continue
        listed.append({
            "date": row["date"], "form": row["form"], "what": FORMS[row["form"]],
            "about": [ITEMS[item] for item in row["items"] if item in ITEMS],
            "url": DOCUMENT_URL.format(cik=found["cik"], accession=row["accession"].replace("-", ""),
                                       document=row["document"]) if row["accession"] and row["document"] else None})
    return {"symbol": found["symbol"], "company": found["name"], "since": since, "filings": listed[:15],
            "more": max(0, len(listed) - 15),
            "notes": ([f"today's read failed, showing the copy kept earlier: {stale}"] if stale else [])
            + ["the list says what was filed, not what it contains: open the link before describing a filing"]}


def periods(facts: dict, tag: str) -> list[dict]:
    units = (((facts.get("facts") or {}).get("us-gaap") or {}).get(tag) or {}).get("units") or {}
    rows = []
    for row in units.get("USD") or []:
        try:
            start, end = datetime.date.fromisoformat(row["start"]), datetime.date.fromisoformat(row["end"])
        except (KeyError, ValueError):
            continue
        rows.append({"start": start, "end": end, "days": (end - start).days, "value": row.get("val"),
                     "filed": row.get("filed", "")})
    return rows


def series(rows: list[dict], low: int, high: int) -> list[dict]:
    """Une valeur par fin de période, la dernière déposée, pour les durées de `low` à `high` jours."""
    kept = {}
    for row in rows:
        if low <= row["days"] <= high and row["value"] is not None:
            if row["end"] not in kept or row["filed"] > kept[row["end"]]["filed"]:
                kept[row["end"]] = row
    return [kept[end] for end in sorted(kept)]


def growth(rows: list[dict]) -> float | None:
    """La variation de la dernière période sur la même un an plus tôt, en pour cent."""
    if not rows:
        return None
    last = rows[-1]
    for row in rows[:-1]:
        if abs((last["end"] - row["end"]).days - 365) <= 20 and row["value"]:
            return round((last["value"] / row["value"] - 1) * 100, 1)
    return None


def figures(symbol: str, *, opener=urllib.request.urlopen, now: datetime.datetime | None = None) -> dict:
    """Le chiffre d'affaires et le résultat net que la société déclare, par trimestre et par an."""
    now = now or client_book.now_utc()
    found, error = company(symbol, opener, now)
    if found is None:
        return {"error": error}
    facts, stale = fetch(f"facts-{found['cik']}.json", FACTS_URL.format(cik=found["cik"]), MAX_AGE_S, opener, now)
    if facts is None:
        return {"error": f"the company's declared figures are unavailable: {stale}"}
    revenue = max((periods(facts, tag) for tag in REVENUE_TAGS),
                  key=lambda rows: max((row["end"] for row in rows), default=datetime.date.min))
    income = periods(facts, INCOME_TAG)

    def table(rows: list[dict], low: int, high: int, count: int) -> list[dict]:
        return [{"period_end": row["end"].isoformat(), "value_usd": row["value"]} for row in series(rows, low, high)[-count:]]

    out = {"symbol": found["symbol"], "company": found["name"], "currency": "USD",
           "revenue": {"quarters": table(revenue, 80, 100, 5), "years": table(revenue, 350, 380, 3),
                       "last_quarter_vs_a_year_earlier_pct": growth(series(revenue, 80, 100)),
                       "last_year_vs_the_year_before_pct": growth(series(revenue, 350, 380))},
           "net_income": {"quarters": table(income, 80, 100, 5), "years": table(income, 350, 380, 3),
                          "last_quarter_vs_a_year_earlier_pct": growth(series(income, 80, 100))},
           "notes": ([f"today's read failed, showing the copy kept earlier: {stale}"] if stale else [])
           + ["figures as the company declared them to the SEC, in US dollars; a fourth quarter often exists "
              "only inside the annual figure, and the latest quarter appears once its quarterly report is filed, "
              "a few weeks after the results; this says what the business earned, not what the stock is worth"]}
    if not out["revenue"]["quarters"] and not out["revenue"]["years"]:
        out["notes"].append("no revenue found under the usual labels: a bank, an insurer or a foreign filer "
                            "reports it differently")
    return out
