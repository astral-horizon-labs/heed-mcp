"""Le profil du client : cinq réponses qui deviennent la règle de son portefeuille.

POURQUOI (2026-11-22, lot 4 du plan grand public). Sans profil, deux investisseurs
reçoivent la même réponse à « comment va mon portefeuille ? », alors que seize actions
cassées n'appellent pas la même chose chez celui qui vend ce qui casse et chez celui qui
garde dix ans. Écrire un plan par action est ingérable à cinquante lignes (décision du
propriétaire, 2026-11-21) : le profil remplace ces plans par UNE règle, dite une fois.

CINQ QUESTIONS, pas davantage :
  1. l'horizon : quand il aura besoin de cet argent ;
  2. la perte supportable : jusqu'où le portefeuille peut tomber sous ce qu'il a payé ;
  3. la part maximale du portefeuille sur une seule action ;
  4. ce qu'il fait d'une action cassée ;
  5. ce qu'il refuse d'acheter.

CE QUE LE PROFIL CHANGE. Les outils confrontent le livre à ces réponses par un calcul
(perte face à la limite, poids de chaque ligne face à la part maximale, lignes cassées
face à sa règle) et rendent des phrases qui nomment SA règle. L'assistant la cite (« by your
rule… ») : c'est la règle du client, pas un signal de Tradewind. La mesure du lot 1
reste vraie et reste dite : un état ne prédit pas la suite.

Le profil vit dans le dossier du livre du client, sur sa machine. Rien n'est exigé : un
profil vide laisse les outils répondre comme avant, et propose les questions.
"""
from __future__ import annotations

import datetime
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
for folder in (ROOT / "scripts", pathlib.Path(__file__).resolve().parent):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import atomic_file  # noqa: E402  # type: ignore[import-not-found]
import client_plans  # noqa: E402

PROFILE_FILE = "profile.json"
HORIZONS = {
    "under_a_year": "the money is needed within a year: a fragile or broken holding matters now",
    "one_to_five_years": "the money is needed in one to five years: a broken holding is worth a decision, a bad week is not",
    "over_five_years": "the money is not needed for more than five years: weekly moves are noise, a holding broken for months is not",
}
WHEN_BROKEN = {
    "review": "you look at a broken stock and decide case by case",
    "trim": "you sell half of a broken stock",
    "exit": "you sell a broken stock",
    "hold": "you keep a broken stock: you invest for the long run",
}
QUESTIONS = [
    {"field": "horizon", "ask": "When will you need this money?",
     "answers": {"under_a_year": "within a year", "one_to_five_years": "in one to five years",
                 "over_five_years": "not for more than five years"}},
    {"field": "max_loss_pct", "ask": "How far below what you paid can your portfolio fall before you would want out? "
                                    "A percentage, for example 10, 20 or 35."},
    {"field": "max_weight_pct", "ask": "What is the largest share of your portfolio you accept in a single stock? "
                                      "A percentage, for example 5, 10 or 25."},
    {"field": "when_broken", "ask": "What do you do when one of your stocks breaks its trend?",
     "answers": {"review": "I look and decide case by case", "trim": "I sell half", "exit": "I sell it",
                 "hold": "I keep it, I invest for the long run"}},
    {"field": "never_buy", "ask": "Is there anything you refuse to buy? Sectors or kinds of companies, or nothing."},
]
FIELDS = tuple(question["field"] for question in QUESTIONS)
#: Une réponse d'une version antérieure, que plus rien ne lit : le nombre d'actions à suivre,
#: remplacé le 2026-11-22 par la part maximale (décision du propriétaire).
RETIRED = ("target_holdings",)
OFFER = ("no profile yet. After the source line, add ONE sentence: five quick questions (when they need "
         "the money, the loss they can bear, the largest share they accept in one stock, what they do with a "
         "broken stock, what they refuse to buy) would let Tradewind read the portfolio by their own "
         "rule. Offer it once, never insist")
STATE_WORDS = {"holds": "holds", "fragile": "is fragile", "broken": "is broken"}
HOW_TO_USE = ("cite the user's own rule in their words (\"by your rule…\"): it is their rule, not a "
              "Tradewind signal, and a state still does not forecast what a stock does next")


def profile_path() -> pathlib.Path:
    return client_plans.book_dir() / PROFILE_FILE


def read() -> dict:
    try:
        found = json.loads(profile_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}


def describe(profile: dict) -> dict:
    """Le profil tel qu'il se dit : chaque réponse, sa phrase, et ce qui reste à demander."""
    rules = {}
    if profile.get("horizon") in HORIZONS:
        rules["horizon"] = {"yours": profile["horizon"], "means": HORIZONS[profile["horizon"]]}
    if profile.get("max_loss_pct") is not None:
        rules["max_loss_pct"] = {"yours": profile["max_loss_pct"],
                                 "means": f"you want out if the portfolio falls {profile['max_loss_pct']:g}% below what you paid"}
    if profile.get("max_weight_pct") is not None:
        rules["max_weight_pct"] = {"yours": profile["max_weight_pct"],
                                   "means": f"you accept at most {profile['max_weight_pct']:g}% of the portfolio in one stock"}
    if profile.get("when_broken") in WHEN_BROKEN:
        rules["when_broken"] = {"yours": profile["when_broken"], "means": WHEN_BROKEN[profile["when_broken"]]}
    if profile.get("never_buy"):
        rules["never_buy"] = {"yours": profile["never_buy"],
                              "means": "you refuse to buy: " + ", ".join(profile["never_buy"])}
    missing = [question for question in QUESTIONS if question["field"] not in rules
               and not (question["field"] == "never_buy" and "never_buy" in profile)]
    return {"set": bool(rules), "rules": rules, "still_to_ask": missing,
            "updated_on": profile.get("updated_on"),
            **({"how_to_use": HOW_TO_USE} if rules else
               {"offer": OFFER})}


def get() -> dict:
    return describe(read())


def update(horizon: str | None = None, max_loss_pct: float | None = None, max_weight_pct: float | None = None,
           when_broken: str | None = None, never_buy: list[str] | None = None, *,
           now: datetime.datetime | None = None) -> dict:
    """Pose une ou plusieurs réponses ; celles qu'on ne donne pas restent comme elles étaient.
    Une réponse invalide refuse tout l'appel, sans rien écrire."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    profile = read()
    problems = []
    if horizon is not None:
        if horizon not in HORIZONS:
            problems.append(f"horizon must be one of: {', '.join(HORIZONS)}")
        else:
            profile["horizon"] = horizon
    if max_loss_pct is not None:
        if not 0 < max_loss_pct < 100:
            problems.append("max_loss_pct must be a percentage between 0 and 100")
        else:
            profile["max_loss_pct"] = float(max_loss_pct)
    if max_weight_pct is not None:
        if not 0 < max_weight_pct <= 100:
            problems.append("max_weight_pct must be a percentage between 0 and 100")
        else:
            profile["max_weight_pct"] = float(max_weight_pct)
    if when_broken is not None:
        if when_broken not in WHEN_BROKEN:
            problems.append(f"when_broken must be one of: {', '.join(WHEN_BROKEN)}")
        else:
            profile["when_broken"] = when_broken
    if never_buy is not None:
        profile["never_buy"] = [term.strip() for term in never_buy if term and term.strip()]
    if problems:
        return {"error": "; ".join(problems)}
    for key in RETIRED:
        profile.pop(key, None)
    profile["updated_on"] = now.date().isoformat()
    path = profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_file.write_text(path, json.dumps(profile, ensure_ascii=False, indent=2) + "\n")
    return describe(profile)


def refused(never_buy: list[str], baskets: list[str], symbol: str) -> list[str]:
    """Les refus du client que les paniers du titre nomment en toutes lettres. Un refus
    que rien ne nomme n'est pas écarté pour autant : l'assistant le juge, il le sait."""
    names = " ".join(baskets + [symbol]).lower()
    return [term for term in never_buy if term.lower() in names]


def for_book(broken: list[dict], cost: float | None, value: float | None,
             loss_if_fragile_break: float | None, weights: list[dict] | None = None,
             profile: dict | None = None) -> dict:
    """Le livre face au profil : ce que chacune de ses règles dit aujourd'hui."""
    profile = read() if profile is None else profile
    out = describe(profile)
    if not out["set"]:
        return out
    checks = []
    limit = profile.get("max_loss_pct")
    if limit is not None and cost and value is not None:
        now_pct = round((value / cost - 1) * 100, 2)
        after = round(((value + (loss_if_fragile_break or 0)) / cost - 1) * 100, 2)
        past = now_pct <= -limit
        checks.append({
            "rule": "max_loss_pct", "yours": limit, "against_what_you_paid_pct": now_pct,
            "if_the_fragile_break_pct": after, "past_your_limit": past,
            "says": (f"the portfolio is {abs(now_pct):g}% {'below' if now_pct < 0 else 'above'} what you paid; "
                     f"your limit is {limit:g}% below"
                     + (": you are past it" if past else
                        f", and it would be at {after:+g}% if every fragile holding broke"))})
    ceiling = profile.get("max_weight_pct")
    if ceiling is not None:
        # Une ligne trop lourde ET cassée passe devant : c'est elle qui fait mal.
        order = {"broken": 0, "fragile": 1, "holds": 2}
        over = sorted((row for row in weights or [] if (row.get("weight_pct") or 0) > ceiling),
                      key=lambda row: (order.get(row.get("state"), 3), -row["weight_pct"]))
        checks.append({
            "rule": "max_weight_pct", "yours": ceiling,
            "over_your_limit": [{key: row.get(key) for key in ("symbol", "weight_pct", "state")} for row in over],
            "says": (f"your limit is {ceiling:g}% of the portfolio in one stock: "
                     + ("; ".join(f"{row['symbol']} is {row['weight_pct']:g}% and {STATE_WORDS.get(row.get('state'), 'is unread')}"
                                  for row in over[:5])
                        + (f", and {len(over) - 5} more" if len(over) > 5 else "") if over
                        else "no holding is above it"))})
    rule = profile.get("when_broken")
    if rule in WHEN_BROKEN:
        names = [row["symbol"] for row in broken]
        checks.append({
            "rule": "when_broken", "yours": rule, "applies_to": names,
            "says": (f"your rule: {WHEN_BROKEN[rule]}. "
                     + (f"{len(names)} holding(s) are broken today" if names else "no holding is broken today"))})
    if profile.get("horizon") in HORIZONS:
        checks.append({"rule": "horizon", "yours": profile["horizon"], "says": HORIZONS[profile["horizon"]]})
    return {**out, "checks": checks}


def for_stock(symbol: str, state: str, held: bool, weight_pct: float | None, baskets: list[str],
              profile: dict | None = None) -> dict:
    """Un titre face au profil : son poids et la règle des cassées s'il est détenu, ses
    refus s'il ne l'est pas."""
    profile = read() if profile is None else profile
    out = describe(profile)
    if not out["set"]:
        # Les questions se proposent sur le portefeuille, pas à chaque titre regardé.
        return {"set": False}
    checks = []
    rule = profile.get("when_broken")
    if held and state == "broken" and rule in WHEN_BROKEN:
        checks.append({"rule": "when_broken", "yours": rule,
                       "says": f"your rule: {WHEN_BROKEN[rule]}. {symbol} is broken"})
    ceiling = profile.get("max_weight_pct")
    # Sous la limite, le poids ne se dit pas : une règle respectée n'est pas une nouvelle.
    if held and ceiling is not None and weight_pct is not None and weight_pct > ceiling:
        checks.append({"rule": "max_weight_pct", "yours": ceiling, "weight_pct": weight_pct, "over_your_limit": True,
                       "says": (f"{symbol} is {weight_pct:g}% of your portfolio; your limit is {ceiling:g}% in one "
                                "stock: it is above it")})
    never = profile.get("never_buy") or []
    if not held and never:
        named = refused(never, baskets, symbol)
        checks.append({"rule": "never_buy", "yours": never, "named_by_its_baskets": named,
                       "says": (f"{symbol} belongs to what you refuse to buy: {', '.join(named)}" if named else
                                f"you refuse to buy: {', '.join(never)}; check {symbol} against it, "
                                "its baskets do not name any of them")})
    if profile.get("horizon") in HORIZONS:
        checks.append({"rule": "horizon", "yours": profile["horizon"], "says": HORIZONS[profile["horizon"]]})
    return {**out, "checks": checks}
