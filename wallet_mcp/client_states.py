"""L'état d'un titre lu sur son graphique : il tient, il est fragile, il a cassé.

POURQUOI (2026-11-21, décision du propriétaire). À cinquante actions, écrire et tenir un
plan par ligne est ingérable : « tout ce qui est plan, tripwire, c'est très compliqué à
gérer dans la vraie vie ». L'état remplace cette charge : il se recalcule à chaque
question sur les clôtures hebdomadaires réglées, sans rien d'écrit, et le livre se lit
par exception (« 44 tiennent, 4 sont fragiles, 2 sont cassées »).

LA RÈGLE, retenue par lui après mesure (définition A) :
  - cassé : deux clôtures de suite sous la tendance de dix semaines, la dernière aussi
    sous celle de trente ;
  - tient : clôture au-dessus de la tendance de dix semaines, et le titre fait mieux
    que le marché que sa propre moyenne de dix semaines ;
  - fragile : tout le reste.

CE QUE LA MESURE A DIT, et que chaque réponse doit porter. Sur 733 actions et dix ans
de clôtures hebdomadaires (au 20/11/2026), aucune des quatre définitions essayées ne
prédit la suite : trois mois après, l'écart médian avec le marché est le même pour les
trois états. Sortir à chaque cassure a ramené la pire baisse d'un portefeuille à parts
égales de −34 % à −21 % et son gain annuel de +20,0 % à +13,6 %, et dans 72 % des cas
le titre est redevenu « tient » plus haut qu'à la sortie. L'état est donc une LECTURE,
jamais un ordre de vente : `READING` le dit dans chaque résultat.

L'humeur du marché (`market_mood`) croise l'état du S&P 500 avec les deux alertes de
peur de la méthode. Elle n'a pas été mesurée comme signal, et la même étude montre que
vendre quand le marché casse a été le pire moment : elle se dit aussi comme une lecture.
"""
from __future__ import annotations

import datetime
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
for folder in (ROOT / "scripts", pathlib.Path(__file__).resolve().parent):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import client_book  # noqa: E402
import client_market  # noqa: E402
import client_plans  # noqa: E402
import client_profile  # noqa: E402
import client_regime  # noqa: E402
import client_risk  # noqa: E402

HOLDS, FRAGILE, BROKEN = "holds", "fragile", "broken"
FAST_WEEKS, SLOW_WEEKS = 10, 30
#: Deux clôtures sous la tendance rapide : il faut la moyenne de la semaine d'avant.
MIN_WEEKS = SLOW_WEEKS + 1
YEAR_WEEKS = 52
#: Les deux alertes de peur de la méthode, lues telles quelles par `market_mood`.
FEAR_ALERTS = ("vix-regime-peur", "vix-terme-backwardation")
SUPPORTIVE, CAUTIOUS, DEFENSIVE = "supportive", "cautious", "defensive"

READING = (
    "For you, not to recite: one clause is enough (\"a reading of the chart, not a forecast\"), "
    "and the figures only if the user asks. A state describes the chart, it does not forecast. Measured on 733 stocks over ten years "
    "of weekly closes (to 2026-11-20): three months later the median gap with the market was "
    "the same after holds, fragile and broken. Leaving every broken stock cut the worst "
    "drawdown of an equal-weight book from -34% to -21% and its yearly gain from +20.0% to "
    "+13.6%; 72% of the time the stock was back to holds at a higher price. Never present a "
    "state as a signal to sell or buy: say what the chart shows, and let the user decide "
    "whether their reason to own the stock still stands.")
MOOD_READING = (
    "For you, not to recite. The mood combines the S&P 500's own state with the method's two fear alerts; it has not "
    "been measured as a signal. In the same ten-year study, selling a broken stock while the "
    "market itself was broken was the worst timing: it gained a median 6.5% over the next "
    "three months. A defensive market is a reason not to add risk, never a reason to sell.")


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def state_at(closes: list[float], ratio: list[float], end: int) -> str | None:
    """L'état à la semaine `end` (index inclus), ou None sans assez d'historique."""
    if end + 1 < MIN_WEEKS:
        return None
    close, previous = closes[end], closes[end - 1]
    fast = mean(closes[end - FAST_WEEKS + 1:end + 1])
    fast_before = mean(closes[end - FAST_WEEKS:end])
    slow = mean(closes[end - SLOW_WEEKS + 1:end + 1])
    if close < fast and previous < fast_before and close < slow:
        return BROKEN
    # `>=` : le repère comparé à lui-même a un ratio constant, et doit pouvoir tenir.
    if close > fast and ratio[end] >= mean(ratio[end - FAST_WEEKS + 1:end + 1]):
        return HOLDS
    return FRAGILE


def classify(closes: list[float], bench: list[float]) -> dict | None:
    """L'état du titre sur ses clôtures alignées à celles du repère, avec ce qui le
    ferait casser. None quand l'historique commun est trop court pour le dire."""
    if len(closes) < MIN_WEEKS or len(closes) != len(bench):
        return None
    ratio = [own / other for own, other in zip(closes, bench)]
    last = len(closes) - 1
    state = state_at(closes, ratio, last)
    weeks = 1
    while weeks <= YEAR_WEEKS and state_at(closes, ratio, last - weeks) == state:
        weeks += 1
    close = closes[last]
    fast, slow = mean(closes[-FAST_WEEKS:]), mean(closes[-SLOW_WEEKS:])
    # Il casse en clôturant sous ses deux tendances : le niveau est la plus basse de
    # celles qui le portent encore. Sous les deux depuis une semaine, il est au bord.
    supports = [trend for trend in (fast, slow) if close > trend]
    level = None if state == BROKEN or not supports else min(supports)
    year = closes[-YEAR_WEEKS:]

    def change(weeks_back: int, series: list[float]) -> float | None:
        return round((series[-1] / series[-1 - weeks_back] - 1) * 100, 2) if len(series) > weeks_back else None

    own_13, bench_13 = change(13, closes), change(13, bench)
    return {
        "state": state,
        "weeks_in_state": weeks if weeks <= YEAR_WEEKS else f"more than {YEAR_WEEKS}",
        "close": close,
        "week_pct": change(1, closes),
        "change_13w_pct": own_13,
        "vs_market_13w_pts": round(own_13 - bench_13, 2) if None not in (own_13, bench_13) else None,
        "below_52w_high_pct": round((1 - close / max(year)) * 100, 2),
        "trend_10w": round(fast, 4), "trend_30w": round(slow, 4),
        "breaks_below": round(level, 4) if level else None,
        "distance_to_break_pct": round((1 - level / close) * 100, 2) if level else None,
        "at_the_edge": state == FRAGILE and not supports,
    }


def week_ending(week: str) -> str:
    """Le vendredi de la semaine, que la série date par son lundi : c'est le jour de la
    clôture citée. Né le 2026-11-22 : un assistant écrivait « clôture du 16/11 » pour
    une clôture du vendredi 20."""
    return (datetime.date.fromisoformat(week) + datetime.timedelta(days=4)).isoformat()


def read_symbol(target: dict, bench: dict[str, float], getter, now: datetime.datetime) -> dict:
    """L'état d'un titre résolu, sur ses semaines communes avec le repère."""
    closes, _, error = client_market.weekly_closes(target["conid"], getter, now)
    if error:
        return {"error": error}
    common = sorted(set(closes) & set(bench))
    found = classify([closes[week] for week in common], [bench[week] for week in common])
    if found is None:
        return {"error": f"fewer than {MIN_WEEKS} settled weeks in common with the market: too short to read"}
    return {"last_settled_week": common[-1], "week_ending": week_ending(common[-1]), **found}


def market_closes(held: list[dict], getter, now: datetime.datetime) -> tuple[dict[str, float], str | None]:
    bench = client_market.resolve(client_market.BENCHMARK, held)
    if bench is None:
        return {}, f"{client_market.BENCHMARK} is missing from the market universe"
    closes, _, error = client_market.weekly_closes(bench["conid"], getter, now)
    return closes, error


def state(symbol: str, getter=None, *, now: datetime.datetime | None = None) -> dict:
    """L'état d'un titre, détenu ou non, et le niveau où il casserait."""
    now = now or client_book.now_utc()
    held = client_market.held_positions(now)
    target = client_market.resolve(symbol, held)
    if target is None:
        return {"error": f"{symbol.upper()} is unknown: neither a holding, nor in the market universe, nor in a basket"}
    if getter is None:
        getter, error = client_market.getter_or_error()
        if error:
            return {"error": error}
    bench, error = market_closes(held, getter, now)
    if error:
        return {"error": error}
    found = read_symbol(target, bench, getter, now)
    if "error" in found:
        return {"error": f"{target['symbol']}: {found['error']}"}
    is_held = target["source"] == "holding"
    weight = None
    if is_held:
        book, _ = client_risk.context(now)
        weight = next((row.get("weight_value_pct") for row in (book or {}).get("rows", {}).values()
                       if row["symbol"].split(" @")[0].upper() == target["symbol"]), None)
    return {"symbol": target["symbol"], "held": is_held, "weight_pct": weight,
            "benchmark": client_market.BENCHMARK, **found,
            "profile": client_profile.for_stock(target["symbol"], found["state"], is_held, weight,
                                                client_market.baskets_of(target["symbol"])),
            "reading": READING}


def book_states(getter=None, *, now: datetime.datetime | None = None) -> dict:
    """Le livre par exception : combien tiennent, lesquelles sont fragiles ou cassées,
    et ce que coûterait la cassure des fragiles."""
    now = now or client_book.now_utc()
    found, error = client_risk.context(now)
    if error:
        return {"error": error}
    if getter is None:
        getter, error = client_market.getter_or_error()
        if error:
            return {"error": error}
    positions = found["snapshot"]["positions"]
    bench, error = market_closes(positions, getter, now)
    if error:
        return {"error": error}
    groups: dict[str, list[dict]] = {HOLDS: [], FRAGILE: [], BROKEN: []}
    unread = []
    for position in positions:
        row = found["rows"][position["contract_description"]]
        symbol = client_plans.ticker(position)
        read = read_symbol({"conid": position["contract_id"]}, bench, getter, now)
        if "error" in read:
            unread.append({"symbol": symbol, "why": read["error"]})
            continue
        names = client_market.baskets_of(symbol)
        groups[read["state"]].append({
            "symbol": symbol, "value_base": row.get("value_base"), "weight_pct": row.get("weight_value_pct"),
            "basket": names[0] if names else None,
            **{key: read[key] for key in ("weeks_in_state", "week_pct", "vs_market_13w_pts",
                                          "breaks_below", "distance_to_break_pct", "at_the_edge")}})
    value = found["book_value"]

    def worth(rows: list[dict]) -> float:
        return sum(row["value_base"] or 0 for row in rows)

    def share(amount: float) -> float | None:
        return round(amount / value * 100, 2) if value else None

    def last_week(rows: list[dict]) -> float:
        """Ce que le groupe a gagné ou perdu sur la dernière semaine, en devise de base."""
        return sum((row["value_base"] or 0) * (1 - 1 / (1 + row["week_pct"] / 100))
                   for row in rows if row["week_pct"] is not None and row["week_pct"] > -100)

    # Né le 2026-11-22 : à « combien je perds si la semaine se répète ? », un assistant
    # écartait les lignes qui tiennent, faute de leur variation dans le résultat.
    moves = {name: round(last_week(rows), 2) for name, rows in groups.items()}
    fragile = sorted(groups[FRAGILE], key=lambda row: row["distance_to_break_pct"] or 0)
    broken = sorted(groups[BROKEN], key=lambda row: row["value_base"] or 0, reverse=True)
    loss = sum((row["value_base"] or 0) * (row["distance_to_break_pct"] or 0) / 100 for row in fragile)
    return {
        "report_date": found["snapshot"]["date"], "base_currency": found["snapshot"]["fx"]["base"],
        "week_ending": week_ending(max(bench)) if bench else None,
        "counts": {name: len(rows) for name, rows in groups.items()},
        "broken": broken, "broken_value_base": round(worth(broken), 2), "broken_value_pct": share(worth(broken)),
        "fragile": fragile, "fragile_value_base": round(worth(fragile), 2),
        "loss_if_fragile_break_base": round(-loss, 2), "loss_if_fragile_break_pct": share(-loss),
        "holds": sorted(row["symbol"] for row in groups[HOLDS]),
        "holds_detail": sorted(({key: row[key] for key in ("symbol", "basket", "week_pct", "vs_market_13w_pts")}
                                for row in groups[HOLDS]), key=lambda row: row["symbol"]),
        "last_week": {"change_base": round(sum(moves.values()), 2), "change_pct": share(sum(moves.values())),
                      "by_state_base": moves,
                      "note": "every holding counted, the ones that hold included; a repeat of the "
                              "same week would cost about the same"},
        "unread": unread,
        "profile": client_profile.for_book(
            broken,
            sum(row.get("cost_base") or 0 for row in found["rows"].values()) or None,
            sum(row.get("value_base") or 0 for row in found["rows"].values()), -loss,
            [{"symbol": row["symbol"], "weight_pct": row["weight_pct"], "state": name}
             for name, rows in groups.items() for row in rows]),
        "how_to_tell_it": ("give the three counts first, then only the broken and the fragile "
                           "holdings; the ones that hold call for nothing and are not listed one by one"),
        "reading": READING,
    }


def market_mood(getter=None, *, now: datetime.datetime | None = None) -> dict:
    """Le marché en un mot : porteur, prudent ou défensif."""
    now = now or client_book.now_utc()
    if getter is None:
        getter, error = client_market.getter_or_error()
        if error:
            return {"error": error}
    index = state(client_market.BENCHMARK, getter, now=now)
    if "error" in index:
        return index
    alerts = client_regime.regime_alerts(getter, now=now)
    if "error" in alerts:
        return alerts
    fear = [alert for alert in alerts["alerts"] if alert["id"] in FEAR_ALERTS]
    lit = [alert for alert in fear if alert["status"] == "triggered"]
    if index["state"] == BROKEN or (index["state"] == FRAGILE and lit):
        mood = DEFENSIVE
    elif index["state"] == FRAGILE or lit:
        mood = CAUTIOUS
    else:
        mood = SUPPORTIVE
    return {
        "mood": mood,
        "last_settled_week": index["last_settled_week"], "week_ending": index["week_ending"],
        "index": {key: index[key] for key in ("symbol", "state", "weeks_in_state", "close", "week_pct",
                                              "change_13w_pct", "below_52w_high_pct")},
        "fear_alerts": [{key: alert.get(key) for key in ("id", "label", "status", "value", "direction")}
                        for alert in fear],
        "how_it_is_decided": ("defensive: the index is broken, or fragile with a fear alert triggered; "
                              "cautious: the index is fragile, or a fear alert is triggered; supportive otherwise"),
        "notes": alerts.get("notes", []),
        "reading": MOOD_READING,
    }
