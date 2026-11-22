# Tradewind — the MCP server for Interactive Brokers investors

Tradewind is a local MCP server for Claude Code and Codex. It reads the market and your
portfolio by price, read-only. Your portfolio is what you tell your assistant ("I hold
50 NVDA bought at 120", or a statement pasted from any broker), or your Interactive
Brokers account through its Flex report. It gives your assistant:

- your book at cost and its holdings;
- your own rule, from five questions asked once (when you need the money, the loss you
  can bear, the largest share you accept in one stock, what you do with a broken stock,
  what you refuse to buy): your portfolio is then read by your rule, and the answer says so;
- your book read by exception, with nothing to write: how many holdings hold, which are
  fragile and which are broken on their weekly chart, the level under which each would
  break, and the market in one word. A reading, not a signal: each result carries what
  ten years of weekly closes say about it;
- a two-year weekly chart of each holding, with your average cost and your plan levels,
  and of any symbol you are studying;
- if you want one, a written plan per holding (thesis, what confirms it, what
  invalidates it, exit, add), tracked at every weekly close, with its review dates and
  its history;
- the risk of each holding and of the whole book if every exit is hit, holdings
  without an exit first;
- the 83 market baskets ranked against SPY after each close, the members of each ranked
  by strength, and relative strength against SPY or against the holding's basket;
- your NAV over time and your drawdowns, measured without deposits and withdrawals;
- market regime alerts, read as a move with a direction, not as a red light.
- what a US-listed company publishes, read from the SEC's public database: when it
  reports next (estimated, with its window) and how much its release weeks have moved,
  which of your holdings report soon, what it filed lately, its revenue and net income.

It sends no orders. Your holdings, your account and your plans stay on your machine; only the IBKR
identifier (conid) of a symbol goes to our price server when a chart or a comparison
needs its prices, and the SEC sees which company's filings your machine reads.

## Install

**Without a broker account**, with Python 3.11 or newer:

```bash
git clone https://github.com/astral-horizon-labs/tradewind.git
cd tradewind
python3 wallet_mcp/install_client.py --no-broker
```

The installer obtains its price server key by itself and registers the `tradewind`
server in Claude Code and Codex. Then tell your assistant what you hold, or paste a
statement, and ask: "how is my portfolio doing?".

Prices come from our server. It already collects about a thousand stocks and funds; a
US stock outside that universe is fetched the first time someone asks for it and
arrives within a few minutes. Stocks listed outside the US are available only when
they belong to one of the 83 market baskets.

**With an Interactive Brokers account**: create a Flex token and a positions query (ten
minutes, once, step by step in
[the installation guide](wallet_mcp/CLIENT.md#1-create-flex-access-in-the-ibkr-portal-ten-minutes-once)),
then run `python3 wallet_mcp/install_client.py --check`. Your holdings then come from
IBKR's nightly report.

Questions and feedback: this repository's issues.
