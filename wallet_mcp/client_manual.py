"""Le livre d'un client sans courtier connecté : ce qu'il détient, dit dans la conversation.

POURQUOI (2026-11-22, lot 3 du plan grand public). Tradewind exigeait un compte IBKR et
une requête Flex : dix minutes de portail avant la première réponse, et personne hors
d'IBKR. Le propriétaire veut un produit « beaucoup plus abordable ». Ici le client dit
« j'ai 50 NVDA à 120 », colle un relevé ou un fichier CSV de n'importe quel courtier, et
le reste du serveur lit ce livre comme il lit un rapport Flex.

COMMENT. Les lignes vivent dans `holdings.json`, dans le dossier du livre du client, sur
sa machine. Pour tout le reste du serveur, elles sont rendues dans le format du rapport
Flex puis lues par `flex_snapshot`, le même lecteur : aucune des fonctions qui lisent un
livre (états, risque, plans, graphique) ne sait d'où il vient.

LES LIMITES, dites au client plutôt que devinées :
  - un titre se résout parmi ceux que le serveur de prix sert (univers de marché et
    paniers). Un titre inconnu est refusé, jamais approché ;
  - le livre a UNE devise. Sans taux de change, une ligne dans une autre devise
    fausserait tous les totaux : elle est refusée ;
  - le prix de marché est la dernière clôture hebdomadaire réglée, pas un cours du jour ;
  - ni liquidités, ni valeur du compte : seulement les lignes ;
  - quand un rapport Flex est configuré, le livre vient d'IBKR et ces outils refusent
    d'écrire : deux sources pour un même livre se contrediraient.
"""
from __future__ import annotations

import csv
import datetime
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
# `flex_snapshot` vit dans le backend du dépôt, et à côté de ce fichier dans le paquet.
for folder in (ROOT / "scripts", ROOT / "dashboard" / "backend", pathlib.Path(__file__).resolve().parent):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import atomic_file  # noqa: E402  # type: ignore[import-not-found]
import client_book  # noqa: E402
import client_market  # noqa: E402
import client_plans  # noqa: E402
import client_prices  # noqa: E402
import flex_snapshot  # noqa: E402  # type: ignore[import-not-found]

HOLDINGS_FILE = "holdings.json"
DEFAULT_CURRENCY = "USD"
ACCOUNT = "MANUAL"
HEADER = ("ClientAccountID,LevelOfDetail,ReportDate,Symbol,Conid,Quantity,MarkPrice,PositionValue,"
          "CostBasisMoney,CostBasisPrice,FXRateToBase,CurrencyPrimary,ListingExchange,AssetClass\n")
SYMBOL_COLUMNS = ("symbol", "ticker", "instrument", "code", "titre", "valeur")
QUANTITY_COLUMNS = ("quantity", "qty", "shares", "units", "position", "quantité", "quantite", "nombre")
PRICE_COLUMNS = ("price", "cost", "average", "avg", "pru", "prix", "coût", "cout")
FLEX_OWNS_THE_BOOK = ("this install reads its holdings from the IBKR Flex report: a trade appears there "
                      "after the nightly batch, and nothing is recorded by hand")


def holdings_path() -> pathlib.Path:
    return client_plans.book_dir() / HOLDINGS_FILE


def read() -> dict:
    """Le livre saisi : `{"currency": …, "holdings": {symbole: ligne}}`, vide s'il n'existe pas."""
    try:
        book = json.loads(holdings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        book = {}
    if not isinstance(book, dict) or not isinstance(book.get("holdings"), dict):
        book = {"holdings": {}}
    book.setdefault("currency", DEFAULT_CURRENCY)
    return book


def write(book: dict) -> None:
    path = holdings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_file.write_text(path, json.dumps(book, ensure_ascii=False, indent=2) + "\n")


def number(text: object) -> float | None:
    """Un nombre tel qu'un relevé l'écrit : « 1,340.50 », « 1 340,50 », « $120 »."""
    if isinstance(text, (int, float)):
        return float(text)
    cleaned = re.sub(r"[^\d,.\-]", "", str(text or ""))
    if not cleaned or not re.search(r"\d", cleaned):
        return None
    if "," in cleaned and "." in cleaned:
        decimal = "," if cleaned.rfind(",") > cleaned.rfind(".") else "."
        cleaned = cleaned.replace("." if decimal == "," else ",", "").replace(decimal, ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", "") if re.fullmatch(r"-?\d{1,3}(,\d{3})+", cleaned) else cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def refusal(symbol: str, quantity: float | None, price: float | None, currency: str | None,
            book: dict) -> tuple[dict | None, str | None]:
    """(titre résolu, raison du refus) : rien n'est écrit sur une ligne douteuse."""
    if client_book.read_config()[1] is None:
        return None, FLEX_OWNS_THE_BOOK
    target = client_market.resolve(symbol)
    if target is None:
        return None, (f"{symbol.strip().upper()} is not among the stocks Tradewind has prices for: "
                      "nothing recorded")
    if quantity is None or quantity <= 0:
        return None, "the quantity must be a positive number"
    if price is None or price <= 0:
        return None, "the cost price must be a positive number"
    wanted = (currency or book["currency"]).strip().upper()
    if book["holdings"] and wanted != book["currency"]:
        return None, (f"the book is kept in {book['currency']} and has no exchange rate: a holding "
                      f"in {wanted} would distort every total, so it is not recorded")
    return {**target, "currency": wanted}, None


def describe(symbol: str, row: dict | None, book: dict) -> dict:
    out = {"symbol": symbol, "currency": book["currency"], "holdings_count": len(book["holdings"])}
    if row:
        out.update(quantity=row["quantity"], average_price=row["average_price"],
                   cost=round(row["quantity"] * row["average_price"], 2))
    return out


def add(symbol: str, quantity: float, price: float, currency: str | None = None, *,
        now: datetime.datetime | None = None) -> dict:
    """Un achat : la ligne naît, ou grossit avec un prix de revient moyen recalculé."""
    now = now or client_book.now_utc()
    book = read()
    target, error = refusal(symbol, number(quantity), number(price), currency, book)
    if error:
        return {"error": error}
    quantity, price = number(quantity), number(price)
    name = target["symbol"]
    row = book["holdings"].get(name)
    if row:
        total = row["quantity"] + quantity
        row["average_price"] = round((row["quantity"] * row["average_price"] + quantity * price) / total, 6)
        row["quantity"] = round(total, 6)
        row["updated_on"] = now.date().isoformat()
        event = "increased"
    else:
        book["currency"] = target["currency"]
        row = book["holdings"][name] = {"conid": target["conid"], "quantity": quantity, "average_price": price,
                                        "added_on": now.date().isoformat()}
        event = "added"
    write(book)
    return {"recorded": event, **describe(name, row, book),
            "next": "`state` reads this stock; `book_states` reads the whole book"}


def set_exact(symbol: str, quantity: float, average_price: float, currency: str | None = None, *,
              now: datetime.datetime | None = None) -> dict:
    """La ligne telle qu'elle est : quantité et prix de revient remplacent ce qui était noté."""
    now = now or client_book.now_utc()
    book = read()
    target, error = refusal(symbol, number(quantity), number(average_price), currency, book)
    if error:
        return {"error": error}
    name = target["symbol"]
    before = book["holdings"].get(name)
    if not book["holdings"]:
        book["currency"] = target["currency"]
    book["holdings"][name] = {"conid": target["conid"], "quantity": number(quantity),
                              "average_price": number(average_price),
                              "added_on": (before or {}).get("added_on", now.date().isoformat()),
                              "updated_on": now.date().isoformat()}
    write(book)
    return {"recorded": "replaced" if before else "added", **describe(name, book["holdings"][name], book)}


def remove(symbol: str, quantity: float | None = None, *, now: datetime.datetime | None = None) -> dict:
    """Une vente : toute la ligne, ou `quantity` titres au même prix de revient."""
    now = now or client_book.now_utc()
    if client_book.read_config()[1] is None:
        return {"error": FLEX_OWNS_THE_BOOK}
    book = read()
    name = symbol.strip().upper()
    row = book["holdings"].get(name)
    if row is None:
        return {"error": f"{name} is not in the book: nothing removed"}
    sold = number(quantity) if quantity is not None else None
    if quantity is not None and (sold is None or sold <= 0):
        return {"error": "the quantity must be a positive number"}
    if sold is not None and sold > row["quantity"] + 1e-9:
        return {"error": f"{name}: {row['quantity']} held, {sold} cannot be removed"}
    if sold is None or abs(sold - row["quantity"]) < 1e-9:
        del book["holdings"][name]
        write(book)
        return {"recorded": "removed", **describe(name, None, book)}
    row["quantity"] = round(row["quantity"] - sold, 6)
    row["updated_on"] = now.date().isoformat()
    write(book)
    return {"recorded": "reduced", **describe(name, row, book)}


def columns(header: list[str]) -> dict[str, int] | None:
    """Où sont le titre, la quantité et le prix dans une ligne d'en-tête ; None sinon."""
    found = {}
    for index, cell in enumerate(header):
        name = cell.strip().lower()
        for key, words in (("symbol", SYMBOL_COLUMNS), ("quantity", QUANTITY_COLUMNS), ("price", PRICE_COLUMNS)):
            if key not in found and any(word in name for word in words):
                found[key] = index
                break
    return found if {"symbol", "quantity"} <= set(found) else None


def split(line: str) -> list[str]:
    """Les cellules d'une ligne de relevé, quel que soit son séparateur.

    La virgule sépare quand elle donne au moins trois cellules ; sinon c'est un
    séparateur de milliers dans une ligne à espaces (« AAA 1,340 12.5 »). Né le
    2026-11-22 : « NVDA,9,215.33 » se lisait comme une seule cellule, parce que « 9,215 »
    ressemble à un millier, et 42 lignes sur 50 d'un CSV ordinaire étaient écartées. Les
    guillemets d'un CSV protègent une valeur qui contient le séparateur.
    """
    for separator in ("\t", ";", "|"):
        if separator in line:
            return [cell.strip() for cell in next(csv.reader([line], delimiter=separator))]
    by_comma = [cell.strip() for cell in next(csv.reader([line]))]
    if "," in line and (len(by_comma) >= 3 or len(line.split()) < 2):
        return by_comma
    return line.split()


def parse(text: str) -> tuple[list[dict], list[dict]]:
    """(lignes lues, lignes écartées avec leur raison) d'un relevé collé ou d'un CSV."""
    rows, rejected = [], []
    layout = {"symbol": 0, "quantity": 1, "price": 2}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or set(line) <= set("-=_ |"):
            continue
        cells = [cell.strip().strip('"') for cell in split(line)]
        header = columns(cells)
        if header is not None and number(cells[header["quantity"]]) is None:
            layout = header
            continue
        try:
            symbol = cells[layout["symbol"]].upper()
            quantity = number(cells[layout["quantity"]])
            price = number(cells[layout["price"]]) if "price" in layout and len(cells) > layout["price"] else None
        except IndexError:
            rejected.append({"line": raw.strip(), "why": "fewer columns than expected"})
            continue
        if quantity is None:
            rejected.append({"line": raw.strip(), "why": "no readable quantity"})
        elif price is None:
            rejected.append({"line": raw.strip(), "why": "no readable cost price"})
        else:
            rows.append({"symbol": symbol, "quantity": quantity, "price": price, "line": raw.strip()})
    return rows, rejected


def import_text(text: str, replace: bool = False, currency: str | None = None, *,
                now: datetime.datetime | None = None) -> dict:
    """Un relevé collé, de n'importe quel courtier : une ligne par titre, sa quantité et
    son prix de revient. `replace` repart d'un livre vide ; sinon chaque ligne lue
    remplace celle du même titre. Rien n'est écrit si aucune ligne n'est lisible."""
    now = now or client_book.now_utc()
    if client_book.read_config()[1] is None:
        return {"error": FLEX_OWNS_THE_BOOK}
    rows, rejected = parse(text)
    book = {"currency": (currency or DEFAULT_CURRENCY).strip().upper(), "holdings": {}} if replace else read()
    if currency and not book["holdings"]:
        book["currency"] = currency.strip().upper()
    recorded = []
    for row in rows:
        target, error = refusal(row["symbol"], row["quantity"], row["price"], None, book)
        if error:
            rejected.append({"line": row["line"], "why": error})
            continue
        previous = book["holdings"].get(target["symbol"], {})
        book["holdings"][target["symbol"]] = {
            "conid": target["conid"], "quantity": row["quantity"], "average_price": row["price"],
            "added_on": previous.get("added_on", now.date().isoformat()), "updated_on": now.date().isoformat()}
        recorded.append(target["symbol"])
    if not recorded:
        return {"error": "no line could be read: one holding per line, as symbol, quantity, cost price",
                "rejected": rejected}
    write(book)
    return {"recorded": sorted(set(recorded)), "recorded_count": len(set(recorded)), "rejected": rejected,
            "currency": book["currency"], "holdings_count": len(book["holdings"]),
            "next": "`book_states` reads the whole book; say which rejected lines to fix"}


def load(getter=None, *, now: datetime.datetime | None = None) -> dict | None:
    """Le livre saisi, rendu comme `client_book.load_book` rend un rapport Flex ; None
    quand rien n'a été saisi."""
    now = now or client_book.now_utc()
    book = read()
    if not book["holdings"]:
        return None
    if getter is None:
        getter, error = client_prices.server_getter(client_book.prices_config())
        if error:
            return {"error": error}
    folder = client_book.state_dir() / "series"
    lines, notes, last_week = [], [], None
    for symbol, row in sorted(book["holdings"].items()):
        found = client_prices.series(row["conid"], folder, getter, now)
        weeks = client_prices.settled_weeks(found["series"], now.date(), weeks=2) if "series" in found else []
        if not weeks:
            notes.append(f"{symbol}: no settled weekly close on our server, valued at its cost price")
        mark = weeks[-1]["c"] if weeks else row["average_price"]
        last_week = max(last_week or "", weeks[-1]["week"]) if weeks else last_week
        lines.append((symbol, row, mark))
    session = (datetime.date.fromisoformat(last_week) + datetime.timedelta(days=4) if last_week
               else now.date()).strftime("%Y%m%d")
    text = HEADER + "".join(
        f"{ACCOUNT},SUMMARY,{session},{symbol},{row['conid']},{row['quantity']},{mark},"
        f"{row['quantity'] * mark:.2f},{row['quantity'] * row['average_price']:.2f},{row['average_price']},"
        f"1,{book['currency']},,STK\n" for symbol, row, mark in lines)
    snapshot, error = flex_snapshot.build(text, cash_text=None, base=book["currency"])
    if error:
        return {"error": f"unusable hand-kept book: {client_book.english(error)}"}
    notes.insert(0, "hand-kept book: valued at the last settled weekly close, with no cash and no account value")
    return {"snapshot": snapshot, "fetched_at": now.isoformat(timespec="seconds"), "notes": notes,
            "source": "manual"}
