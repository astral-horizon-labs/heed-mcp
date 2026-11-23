"""À qui est le livre qu'on lit : un seul client sur sa machine, ou un utilisateur parmi d'autres.

POURQUOI (2026-11-22, lot 6 du plan grand public). Installé chez un client, le serveur
lit UN livre, dans un dossier que désigne une variable d'environnement. Hébergé derrière
une URL, le même code sert plusieurs personnes : le livre à lire dépend de celle qui
pose la question. Ce module porte ce seul choix, pour que rien d'autre n'ait à savoir
si le serveur est hébergé.

LA RÈGLE QUI COMPTE. En mode hébergé, un appel sans utilisateur identifié LÈVE. Il ne
retombe jamais sur un dossier par défaut : ce serait montrer à quelqu'un le portefeuille
d'un autre, ou mêler les leurs.

Ce qui est par utilisateur : son dossier de livre (lignes, profil, plans). Ce qui est
commun : les séries de prix, le classement des paniers et les dépôts de la SEC gardés en
cache, qui sont des données de marché.
"""
from __future__ import annotations

import pathlib
from typing import Callable

#: Rend le dossier du livre de l'utilisateur courant. Posé par le serveur hébergé.
_resolver: Callable[[], pathlib.Path] | None = None


class TenantError(RuntimeError):
    """Aucun utilisateur identifié, ou plus de place : le message se montre tel quel."""


def serve_many(resolver: Callable[[], pathlib.Path]) -> None:
    """Passe le processus en mode hébergé : `resolver` désigne le livre à chaque appel."""
    global _resolver
    _resolver = resolver


def serve_one() -> None:
    """Revient au mode d'un seul client (les tests)."""
    global _resolver
    _resolver = None


def hosted() -> bool:
    return _resolver is not None


def book_dir() -> pathlib.Path | None:
    """Le dossier du livre de l'utilisateur courant en mode hébergé ; None sur la machine
    d'un seul client, où le dossier vient de l'environnement."""
    return _resolver() if _resolver is not None else None
