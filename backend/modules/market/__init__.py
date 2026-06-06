"""modules/market — Market feature module (Sprint 3, SPEC §S8).

Crypto quotes via CoinGecko free API (fail-open), ETF/VN via deterministic mock;
changePct derived server-side from price_history; rule-based price alerts +
macro signal stubs. The registry discovers MODULE from router.py (T2).
"""
