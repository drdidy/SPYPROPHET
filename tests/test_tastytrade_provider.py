from __future__ import annotations

import math
from tastytrade_provider import TastytradeProvider, TastytradeProviderStatus


def test_status_defaults():
    st = TastytradeProviderStatus()
    assert st.connected is False and st.auth_ok is False


def test_auth_failure(monkeypatch):
    p = TastytradeProvider("id","secret","refresh")
    class R: status_code=401
    monkeypatch.setattr("requests.post", lambda *a, **k: R())
    assert p.authenticate() is False
    assert p.get_status()["auth_ok"] is False


def test_chain_selection_exact_and_nearest(monkeypatch):
    p = TastytradeProvider("id","secret","refresh")
    monkeypatch.setattr(p, "get_nested_option_chain", lambda *a, **k: {"data":{"items":[{"underlying-symbol":"SPY","expirations":[{"expiration-date":"2026-04-29","strikes":[{"strike-price":"709.0","call":"C709","put":"P709"},{"strike-price":"716.0","call":"C716","put":"P716"}]}]}]}})
    c,pu,w = p.select_contracts("SPY","2026-04-29",709,716)
    assert c["symbol"]=="C709" and pu["symbol"]=="P716" and w is None

    c2,pu2,w2 = p.select_contracts("SPY","2026-04-29",710,715)
    assert w2 is not None and c2 and pu2


def test_chain_selection_legacy_shape(monkeypatch):
    p = TastytradeProvider("id","secret","refresh")
    monkeypatch.setattr(p, "get_nested_option_chain", lambda *a, **k: {"data":{"items":[{"expiration-date":"2026-04-29","calls":[{"strike-price":709,"symbol":"C709"}],"puts":[{"strike-price":716,"symbol":"P716"}]}]}})
    c,pu,w = p.select_contracts("SPY","2026-04-29",709,716)
    assert c["symbol"]=="C709" and pu["symbol"]=="P716" and w is None


def test_chain_endpoint(monkeypatch):
    p = TastytradeProvider("id","secret","refresh")
    p.access_token = "token"
    class R:
        status_code = 200
        def json(self):
            return {"data":{"items":[]}}
    calls = []
    monkeypatch.setattr("requests.get", lambda url, **kwargs: calls.append((url, kwargs)) or R())
    assert p.get_nested_option_chain("SPY","2026-04-29") == {"data":{"items":[]}}
    assert calls[0][0].endswith("/option-chains/SPY/nested")


def test_expiration_unavailable(monkeypatch):
    p = TastytradeProvider("id","secret","refresh")
    monkeypatch.setattr(p, "get_nested_option_chain", lambda *a, **k: {"data":{"items":[]}})
    c,pu,w = p.select_contracts("SPY","2026-04-29",709,716)
    assert c is None and pu is None and "Expiration" in w


def test_quote_conversion_and_missing_greeks():
    p = TastytradeProvider("id","secret","refresh")
    q = p._to_quote_dict({"strike-price":709,"symbol":"C","bid":1.0,"ask":1.2}, "CALL", 712)
    assert q["mark"] == 1.1 and q["spread"] == 0.19999999999999996
    assert math.isnan(q["delta"]) and math.isnan(q["iv"])


def test_no_order_methods():
    banned=["submit_order","place_order","dry_run_order","cancel_order","replace_order"]
    for b in banned:
        assert not hasattr(TastytradeProvider, b)
