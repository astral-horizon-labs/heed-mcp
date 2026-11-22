#!/usr/bin/env python3
"""MCP WALLET, MODE CLIENT — le livre d'un investisseur lu par son propre Flex.

    python wallet_mcp/client_server.py      serveur stdio (Claude Code, Codex, Claude Desktop)

POURQUOI UN SECOND SERVEUR (2026-11-07). `server.py` sert le livre du propriétaire
par son backend (`:8000`, Gateway, planificateur) ; un client n'a rien de tout cela.
Celui-ci ne parle qu'à IBKR, par le Flex Web Service et le jeton du client
(`client_book.py`), et garde le rapport sur la machine du client. Les deux serveurs
restent séparés plutôt qu'un seul à deux modes : un client ne doit jamais voir un
outil qui chercherait un backend qu'il n'a pas.

LOT 1 : le livre au coût (`book_summary`, `positions`) et l'état de la configuration
(`setup_status`). LOT 2 (même jour) : le graphique hebdomadaire d'une ligne
(`weekly_chart`), sur les prix de NOTRE serveur (`client_prices.py`), décision du
propriétaire. LOT 3 (même jour) : le plan de chaque ligne (`plan`, `set_plan`,
`plans_overview`), écrit chez le client et suivi sur nos prix (`client_plans.py`).
LOT 4 (même jour) : les alertes de régime de la méthode (`regime_alerts`), évaluées sur
nos prix (`client_regime.py`). LOT 6 (même jour, « tous les tools possibles ») : le
marché (`relative_strength`, `basket`, `weekly_chart` d'un titre non détenu,
`client_market.py`), le risque face aux sorties (`position_risk`, `book_risk`), les
revues (`reviews_due`, `plan_history`, `client_risk.py`), la NAV et ses creux
(`nav_history`, `drawdowns`, `client_nav.py`, deux requêtes Flex facultatives).

CE QU'IL NE FAIT PAS : aucun ordre, aucune écriture hors de la machine du client (son
cache local et les plans de son livre, sous son répertoire de données). Ce qui sort de la machine : la requête Flex vers IBKR, et
vers notre serveur de prix le seul conid de la ligne dont on demande le graphique —
ni quantité, ni coût, ni valeur.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from mcp.server.mcpserver import Image, MCPServer  # noqa: E402

import client_book  # noqa: E402
import client_edgar  # noqa: E402
import client_manual  # noqa: E402
import client_market  # noqa: E402
import client_nav  # noqa: E402
import client_plans  # noqa: E402
import client_profile  # noqa: E402
import client_regime  # noqa: E402
import client_risk  # noqa: E402
import client_states  # noqa: E402

INSTRUCTIONS = """\
Tradewind reads the market and the user's Interactive Brokers book by price, read-only.
For any question about the market, a stock or their portfolio, call THESE tools first.

HOW TO ANSWER, every time:
1. One sentence first: the verdict, in plain words.
2. The chart, when a chart tool drew one: it is shown to the user, so point at what it
   shows in one sentence. With no chart, go straight to the points: never mention a
   chart you did not draw, nor why.
3. At most three short points, each figure with its date.
4. A line starting with "Next:" (translated: "À faire :", "Siguiente:") and one thing to
   do, or "Next: nothing to do."
5. A last line saying where the figures come from, in these exact words: "Computed by
   Tradewind on the closes of <date>." Anything you add from your own knowledge (what a company does, news, a
   forecast) goes AFTER that line, in one sentence introduced by "General view, not
   verified by Tradewind:". Never mix the two, and leave it out when you have nothing.
HARD LIMIT: 150 words for the whole answer, unless the user asks for more. It is read
on a phone. Three points means three lines, not three paragraphs, with no list inside
a point; name at most five stocks; leave out what the user did not ask (cost, NAV,
setup) unless it is the point.
A tool's `reading`, `legend` or `how_to_tell_it` is guidance for you, never text to
repeat. Answer in the user's language, translating the five parts and the state words.

DATES. A weekly close is the Friday close: quote `week_ending`. Where a tool only gives
`last_settled_week`, that date is the Monday starting the week and the close is the
Friday four days later: quote that Friday, in the source line too.

PLAIN WORDS. A stock holds, is fragile or is broken; the market is supportive, cautious
or defensive; a stock does better or worse than the market. Say "its ten-week trend",
never "SMA", "moving average", "ratio" or "basis points", unless the user used the word.

WHICH TOOLS FOR WHICH QUESTION:
- "Where is the market?": `market_mood`, then `basket_ranking` for what leads and what
  lags, and `weekly_chart` of SPY.
- "What is strong right now?": `basket_ranking`, then `basket` on two or three leading
  baskets, then `state` or `weekly_chart` of one stock in each. Three to five names, one
  line each; the market itself is another question.
- "What do you think of X?": `state` of X, its `weekly_chart` and its `earnings` (when it
  reports next, and how much its release weeks have moved); `relative_strength` with
  against="basket" when it belongs to a basket.
- "What does the company earn?" / "what did it publish?": `figures` (revenue and net
  income as declared) and `filings` (what it filed lately, with links).
- "How is my portfolio doing?": `book_states`, with `book_summary` for its value. Give
  the three counts first, then only the broken and the fragile holdings.
- "What should I look at?": `book_states`, `market_mood` and `upcoming_earnings` (the
  holdings that report soon); `plans_overview` when the user has written plans. Three
  subjects at most, or "nothing calls for a decision".
- "Which sectors are taking over?": `basket_ranking`, comparing four weeks with thirteen.
- "Which of my stocks lag their sector?": `book_states` and `basket_ranking`, two calls:
  a holding lags when its `vs_market_13w_pts` is well under its `basket`'s 13-week
  `spread_pts`. `relative_strength` against="basket" on one or two names at most.
- "What if the market repeats last week?": `book_states`: `last_week` has what the whole
  book moved, by state, every holding counted.
- "Warn me if X closes the week under N": `set_plan` with one exit level on a holding,
  then `position_risk` for what that exit costs.
- "I bought 20 LLY at 1340" / "I hold…": `add_holding` (a purchase), `set_holding` (the
  exact quantity and cost), `remove_holding` (a sale), then read the stock with `state`.
  A pasted statement or CSV: `import_holdings`, then say what was read and what was not.
  When the book comes from IBKR these tools refuse: say that the trade will appear in
  the report after the nightly batch, then read the stock.
- A new user with no holdings: ask what they hold, or for a statement to paste. No
  broker account is needed.
- "Set up my profile" / an answer to one of the five questions: `set_profile`, with only
  the answers given; `profile` shows what is set and what is still to ask.

THE USER'S PROFILE. Five answers (horizon, bearable loss, largest share in one stock,
what they do with a broken stock, what they refuse to buy) make the rule of their portfolio.
`book_states` and `state` return `profile.checks`: what each rule says today. When a
check applies, say it in the user's own terms, starting with "By your rule" (translated),
and keep the action in "Next:" consistent with it. It is THEIR rule, never a Tradewind
signal. One clause per rule that applies, inside the three points, not a fourth one.
With no profile, `book_states` returns `profile.offer`: answer as usual, then do what it
says, in one sentence after the source line, once in the conversation; never insist.

RULES:
- A results release is the one thing the chart does not hold. Mention the next one
  only when it is expected within four weeks, in one clause; further away, leave it out
  unless the user asks. A release date is always ESTIMATED from the company's rhythm:
  give its window and say "expected around", never a firm date. Say how much the stock moved in past release weeks, never which way it
  will go: the size repeats, the direction does not. Companies that file nothing with
  the SEC (foreign listings, funds) have no date: say so.
- A state is a READING, never a signal: measured over ten years it did not forecast
  what a stock does next (`reading` has the figures, for when the user asks). Say what the
  chart shows and where the stock would break; never tell the user to sell or to buy
  because of a state. A defensive market is a reason not to add risk, not to sell.
- The book is either the IBKR Flex report (the last session IBKR processed, nightly
  batch) or the holdings the user told you, valued at the last weekly close with no cash
  (`source` says which). Quote its `date`, and `notes` when they say data is missing.
- Weights are read at COST (`weight_cost_pct`): the money committed per holding.
  Without a Cash Report query, NAV and cash are `null`: never infer them.
- A holding is judged against its market first: rising less than its basket or SPY
  means the market is not carrying the bet, even in a rise.
- A written plan is optional. A holding the user wants to follow closely can get one
  with `set_plan`, after `weekly_chart`: levels are horizontal, judged on the weekly
  close and justified by the visible candles. Risk is then the money lost if the holding
  goes to its exit (`position_risk`, `book_risk`).
- A regime alert lags by construction: say where the move is heading (`direction`,
  `recent_settled`) and what it changes, in plain words. Name one alert only if it
  teaches something, never "everything is red".
- Call `setup_status` first when a tool returns a configuration error.
- This server sends no orders and writes nothing at IBKR.
"""

mcp = MCPServer("tradewind", instructions=INSTRUCTIONS, log_level="WARNING")


@mcp.tool(description='The book at a glance: session date, NAV and cash (when the cash report is configured), total cost, number of holdings, top ten holdings by weight at cost. `refresh=True` fetches the report from IBKR even if it is under six hours old (~30 s).')
def book_summary(refresh: bool = False) -> dict:
    """Le livre en un coup d'œil : date de la séance, NAV et cash (si le rapport cash est
    configuré), coût total, nombre de lignes, dix premières lignes par poids au coût.
    `refresh=True` retire le rapport chez IBKR même s'il a moins de six heures (~30 s)."""
    return client_book.book_summary(force=refresh)


@mcp.tool(description='Every holding, in base currency: quantity, cost, value, weight at cost and at value, unrealized P&L. Sorted by weight at cost, descending.')
def positions() -> dict:
    """Toutes les lignes, en devise de base : quantité, coût, valeur, poids au coût et à
    la valeur, plus-value latente. Triées par poids au coût décroissant."""
    return client_book.positions()


@mcp.tool(description='The client configuration (file, cash report, base currency) and the age of the cached report. Fetches nothing from IBKR and never reveals the token.')
def setup_status() -> dict:
    """La configuration du client (fichier, rapport cash, devise de base) et l'âge du
    rapport gardé. Ne tire rien chez IBKR et ne révèle jamais le jeton."""
    return client_book.setup_status()


# Sans sortie structurée : l'image suivie de son texte se rend en deux blocs de contenu.
@mcp.tool(structured_output=False, description="Two-year weekly chart of a holding (settled candles, log scale), with the client's average cost as blue dashes and the plan levels as solid lines; also any symbol of the market universe or the baskets the user does not hold. Look at it before any opinion. Grid prices and the last settled close come alongside.")
def weekly_chart(symbol: str) -> list | dict:
    """Graphique hebdomadaire sur deux ans d'une ligne détenue (bougies réglées, échelle
    log), avec le coût moyen du client en tirets bleus. À regarder avant tout avis.
    Les prix des lignes de la grille et la dernière clôture réglée sont rendus à côté."""
    result = client_book.weekly_chart(symbol)
    if "error" in result:
        return result
    png = result.pop("png")
    return [Image(data=png, format="png"), result]


@mcp.tool(description="The method's market regime alerts on settled closes: triggered first, with their latest values, the direction of the move against the threshold, what they mean and what they ask for. Market data only, nothing from the account.")
def regime_alerts() -> dict:
    """Les alertes de régime de la méthode sur les clôtures réglées : franchies d'abord,
    avec leurs dernières valeurs, le sens du mouvement face au seuil, ce qu'elles
    veulent dire et ce qu'elles demandent. Données de marché seules, rien du compte."""
    return client_regime.regime_alerts()


@mcp.tool(description='Every holding against its plan, on settled closes: crossed levels (with what the plan intended), holdings without a plan, holdings without an exit, and the nearest exit of the others.')
def plans_overview() -> dict:
    """Chaque ligne détenue face à son plan, sur les clôtures réglées : niveaux franchis
    (avec ce que le plan prévoyait), lignes sans plan, lignes sans sortie, et la sortie
    la plus proche des autres."""
    return client_plans.overview()


@mcp.tool(description='The plan of one holding: thesis, conditions, next decision, and each level with its effective threshold, the last settled close and the distance.')
def plan(symbol: str) -> dict:
    """Le plan d'une ligne détenue : thèse, conditions, prochaine décision, et chaque
    niveau avec son seuil effectif, la dernière clôture réglée et la distance."""
    return client_plans.get_plan(symbol)


@mcp.tool(description='Writes the active plan of a holding, on the client\'s machine. `horizon`: long or short. One level per line: "1W < 140 (memory) [exit] exit on a weekly close below 140" — bar 1D|1W|1M, < or >, a price, `sma10` or `trail<seed>`, the method in parentheses (memory, fib, pivot, round, faber, net), the effect in brackets (exit, trim, add, warn, review), then the action. Without levels, `no_levels_reason` is required. An invalid plan is rejected as a whole, with all its violations.')
def set_plan(symbol: str, thesis: str, horizon: str, if_hit: str, if_miss: str,
             next_decision: str, levels: list[str] | None = None,
             no_levels_reason: str | None = None, review_by: str | None = None,
             reason: str | None = None) -> dict:
    """Écrit le plan actif d'une ligne détenue, chez le client. `horizon` : long ou short.
    Chaque niveau en une ligne : « 1W < 140 (memory) [exit] sortie si clôture hebdo sous
    140 » — barre 1D|1W|1M, < ou >, un prix, `sma10` ou `trail<seed>`, la méthode entre
    parenthèses (memory, fib, pivot, round, faber, net), l'effet entre crochets (exit,
    trim, add, warn, review), puis l'action. Sans niveau, `no_levels_reason` est exigé.
    Un plan invalide est refusé en entier, avec toutes ses violations."""
    return client_plans.set_plan(symbol, thesis, horizon, if_hit, if_miss, next_decision,
                                 levels, no_levels_reason, review_by, reason)


def with_image(result: dict) -> list | dict:
    if "error" in result:
        return result
    png = result.pop("png")
    return [Image(data=png, format="png"), result]


@mcp.tool(structured_output=False, description='A symbol against a benchmark: the weekly ratio drawn over two years (a rising line means the symbol leads), its performance spread over 4, 13, 26 and 52 weeks, the ratio against its 10-week average and its trend over the last five weeks. `against`: a symbol (default SPY, or QQQ, XLV, IWM…) or "basket" for the equal-weight basket the symbol belongs to. Works for holdings and for any symbol of the market universe or the baskets.')
def relative_strength(symbol: str, against: str = "SPY") -> list | dict:
    """Le titre face à un repère : ratio hebdomadaire dessiné, écart sur 4 à 52 semaines,
    ratio face à sa moyenne de dix semaines. `against` : un symbole ou « basket »."""
    return with_image(client_market.relative_strength(symbol, against))


@mcp.tool(description='A market basket (e.g. "AI", "CNS BIOTECH", "AEROSPACE & DEFENSE"), named or found through one of its members: its members ranked by 13-week strength, and the equal-weight basket against SPY over 4 to 52 weeks. An unknown name lists the 83 baskets.')
def basket(name_or_symbol: str) -> dict:
    """Un panier, nommé ou désigné par un membre : membres classés par force sur 13
    semaines, et le panier équipondéré face au S&P 500. Un nom inconnu liste les paniers."""
    return client_market.basket(name_or_symbol)


@mcp.tool(description='Every market basket (83) ranked against SPY on settled weekly closes: the equal-weight basket\'s spread over 4, 13, 26 and 52 weeks, its ratio to SPY against its 10-week average, the direction of that ratio over five weeks, and its three strongest and weakest members over 13 weeks. Computed on our server after each close, read in one request. Start here to find the baskets that lead before choosing a stock.')
def basket_ranking() -> dict:
    """Les 83 paniers classés face au S&P 500, calculés par notre serveur après chaque clôture."""
    return client_market.ranking()


@mcp.tool(description='What a holding costs if it goes to its nearest exit: the exit threshold and its distance, the loss in base currency and as a share of the book, and the P&L left at the exit. A holding without a plan or without an exit has unbounded risk.')
def position_risk(symbol: str) -> dict:
    """Ce que coûte une ligne si elle va jusqu'à sa sortie la plus proche, en devise de
    base et en part du livre. Sans plan ni sortie : risque non borné."""
    return client_risk.position_risk(symbol)


@mcp.tool(description='The whole book against its exits: holdings with unbounded risk first (no plan or no exit), then the loss to exit of every other holding, and the total loss if every exit is hit.')
def book_risk() -> dict:
    """Le livre face à ses sorties : les lignes au risque non borné d'abord, puis la perte
    jusqu'à la sortie de chaque autre ligne, et la perte si toutes les sorties tombent."""
    return client_risk.book_risk()


@mcp.tool(description='Records a purchase the user tells you, when no broker is connected: the holding is created, or grows with its average cost recomputed. `price` is the price paid per share. Refused for a stock Tradewind has no prices for, for a second currency in the same book, and when the book comes from IBKR.')
def add_holding(symbol: str, quantity: float, price: float, currency: str = "") -> dict:
    """Note un achat dit dans la conversation, sans courtier connecté : la ligne naît, ou
    grossit avec un prix de revient moyen recalculé."""
    return client_manual.add(symbol, quantity, price, currency or None)


@mcp.tool(description='Sets a holding exactly as the user states it, when no broker is connected: this quantity and this average cost replace what was recorded. Use it to correct a holding or to enter one already owned.')
def set_holding(symbol: str, quantity: float, average_price: float, currency: str = "") -> dict:
    """Pose une ligne telle que le client la donne : quantité et prix de revient moyen
    remplacent ce qui était noté."""
    return client_manual.set_exact(symbol, quantity, average_price, currency or None)


@mcp.tool(description='Records a sale the user tells you, when no broker is connected: the whole holding, or `quantity` shares of it at the same average cost.')
def remove_holding(symbol: str, quantity: float = 0) -> dict:
    """Note une vente dite dans la conversation : toute la ligne, ou `quantity` titres."""
    return client_manual.remove(symbol, quantity or None)


@mcp.tool(description='Reads a statement or a CSV pasted by the user, from any broker: one holding per line with its symbol, quantity and cost price, with or without a header row. Returns what was recorded and each rejected line with its reason. `replace=True` starts from an empty book; otherwise a line read replaces the holding of the same symbol.')
def import_holdings(text: str, replace: bool = False, currency: str = "") -> dict:
    """Lit un relevé ou un CSV collé, de n'importe quel courtier : une ligne par titre,
    sa quantité et son prix de revient. Rend ce qui est noté et chaque ligne écartée."""
    return client_manual.import_text(text, replace, currency or None)


@mcp.tool(description="The user's profile: the five answers that make the rule of their portfolio (horizon, bearable loss, largest share in one stock, what they do with a broken stock, what they refuse to buy), each with what it means, and the questions still to ask.")
def profile() -> dict:
    """Le profil du client : ses cinq réponses, ce que chacune veut dire, et les questions
    qui restent à poser."""
    return client_profile.get()


@mcp.tool(description='Records the answers the user gives to the profile questions; an answer not given keeps its value. `horizon`: under_a_year, one_to_five_years or over_five_years. `max_loss_pct`: how far below what they paid the portfolio may fall, in percent. `max_weight_pct`: the largest share of the portfolio they accept in one stock, in percent. `when_broken`: review (decide case by case), trim (sell half), exit (sell) or hold (keep). `never_buy`: what they refuse to buy, as a list; an empty list means nothing.')
def set_profile(horizon: str = "", max_loss_pct: float = 0, max_weight_pct: float = 0,
                when_broken: str = "", never_buy: list[str] | None = None) -> dict:
    """Note les réponses du client aux questions du profil ; une réponse non donnée garde
    sa valeur."""
    return client_profile.update(horizon or None, max_loss_pct or None, max_weight_pct or None,
                                 when_broken or None, never_buy)


@mcp.tool(description='When a US-listed company reports its results: its past release dates (from its SEC filings), the next one ESTIMATED from its own rhythm with a two-week window, and how much the stock moved in the weeks of its past releases (median size, largest fall and rise). Works for any company that files with the SEC, held or not.')
def earnings(symbol: str) -> dict:
    """Quand la société publie ses résultats : ses dates passées, la prochaine estimée
    sur son rythme, et ce que le cours a fait les semaines de ses publications."""
    return client_edgar.earnings(symbol)


@mcp.tool(description='The holdings expected to report their results within `days` days (14 by default), soonest first, each with its estimated window, how much its release weeks have moved and its weight in the book. Reads the SEC once per holding and keeps it twelve hours: the first call on a large book takes a few seconds per ten holdings.')
def upcoming_earnings(days: int = 14) -> dict:
    """Les lignes du livre dont la publication est attendue dans les `days` jours, la plus
    proche d'abord."""
    return client_edgar.upcoming(days=days)


@mcp.tool(description='What a US-listed company filed with the SEC over the last four months, newest first: annual and quarterly reports, event reports with what they are about in plain words (results, an officer change, an agreement, a share offering…), each with its link. It says what was filed, not what it contains.')
def filings(symbol: str) -> dict:
    """Ce que la société a déposé à la SEC ces quatre derniers mois, en mots simples, avec
    le lien de chaque dépôt."""
    return client_edgar.filings(symbol)


@mcp.tool(description='Revenue and net income as a US-listed company declared them to the SEC: the last five quarters and three years, and the change of the last quarter and year on the same period a year earlier. What the business earned, not what the stock is worth.')
def figures(symbol: str) -> dict:
    """Le chiffre d'affaires et le résultat net déclarés à la SEC, par trimestre et par an,
    avec leur variation sur un an."""
    return client_edgar.figures(symbol)


@mcp.tool(description='One stock read from its weekly chart, held or not: it holds, it is fragile or it is broken, for how many weeks, its last settled close, its change over one and thirteen weeks against the market, how far it is from its one-year high, and the level under which it would break. A reading, not a signal: `reading` carries what ten years of prices say about it.')
def state(symbol: str) -> dict:
    """L'état d'un titre lu sur son graphique hebdomadaire : il tient, il est fragile ou
    il a cassé, depuis combien de semaines, et le niveau où il casserait. Une lecture."""
    return client_states.state(symbol)


@mcp.tool(description='The whole book by exception, with nothing written beforehand: how many holdings hold, are fragile or are broken; the broken ones by value, the fragile ones by distance to their breaking level, the money lost if every fragile holding breaks, and the holdings that hold as a plain list. Start here for "how is my portfolio doing?".')
def book_states() -> dict:
    """Le livre par exception, sans rien d'écrit : combien de lignes tiennent, sont fragiles
    ou cassées, les cassées par valeur, les fragiles par distance à leur cassure, et la
    perte si toutes les fragiles cassent."""
    return client_states.book_states()


@mcp.tool(description='The market in one word, supportive, cautious or defensive: the S&P 500 read like any stock (holds, fragile, broken) crossed with the method\'s two fear alerts, with the figures behind the word. A defensive market is a reason not to add risk, never a reason to sell: `reading` says why.')
def market_mood() -> dict:
    """Le marché en un mot, porteur, prudent ou défensif : l'état du S&P 500 croisé avec
    les deux alertes de peur de la méthode."""
    return client_states.market_mood()


@mcp.tool(description='Plans to re-read: review date passed, review within two weeks, plans without a review date (flagged stale after 180 days), and holdings without a plan.')
def reviews_due() -> dict:
    """Les plans à relire : revue dépassée, proche, plans sans date de revue (anciens
    au-delà de 180 jours), lignes sans plan."""
    return client_risk.reviews_due()


@mcp.tool(description="Every rewrite of a symbol's plan on this machine, newest first, with the current plan.")
def plan_history(symbol: str) -> dict:
    """Chaque réécriture du plan d'un titre, la plus récente d'abord, et le plan actuel."""
    return client_risk.plan_history(symbol)


@mcp.tool(description='Account value over time (needs the optional NAV and Cash Transactions Flex queries): month-end NAV, a growth index without deposits and withdrawals, its peak, every deposit and withdrawal. `refresh=True` fetches the reports again.')
def nav_history(refresh: bool = False) -> dict:
    """La NAV en fins de mois, l'indice sans flux et son sommet, chaque apport et retrait
    (requêtes Flex NAV et Cash Transactions facultatives)."""
    return client_nav.nav_history(refresh_now=refresh)


@mcp.tool(description='The book\'s drawdown from its peak, measured without deposits and withdrawals, its worst point, and past episodes of at least 5% with their median: context, not a threshold. Needs the optional NAV Flex query.')
def drawdowns() -> dict:
    """La baisse du livre depuis son sommet, sans les flux, son pire point et les creux
    passés d'au moins 5 % avec leur médiane : du contexte, pas un seuil."""
    return client_nav.drawdowns()


if __name__ == "__main__":
    mcp.run()
