from __future__ import annotations
from datetime import datetime
import pandas as pd
from app import (DynamicLine, MockOptionProvider, SecondaryPivot, TradeSignal, build_options_cockpit_state, get_central_tz, get_default_projection_time, project_option_entry_to_target, resolve_entry_target_lines, simulate_option_scenarios)


def _ts(s): return pd.Timestamp(datetime.fromisoformat(s), tz=get_central_tz())

class Strikes:
    def __init__(self,p,c,pu,e): self.underlying_price=p; self.call_strike=c; self.put_strike=pu; self.expiration_date=e


def _lines():
    t=_ts("2026-04-29T09:00:00")
    return [DynamicLine("UA",714.2,t,0,"ascending","PUT_ZONE","PRIMARY_HIGH",True,""),DynamicLine("UD",711.8,t,0,"descending","CALL_ZONE","PRIMARY_HIGH",True,""),DynamicLine("LA",713.4,t,0,"ascending","PUT_ZONE","PRIMARY_LOW",True,""),DynamicLine("LD",711.2,t,0,"descending","CALL_ZONE","PRIMARY_LOW",True,"")]


def test_mock_provider_and_quote_math():
    p=MockOptionProvider(); q=p.get_selected_quotes(712.61, _ts("2026-04-29").date(), 709,716)
    assert q['call'].provider=='MOCK' and q['put'].provider=='MOCK'
    assert q['call'].bid < q['call'].ask and q['call'].spread == round(q['call'].ask-q['call'].bid,2)
    assert q['call'].mark>0 and q['put'].mark>0


def test_state_selection_signal_types_and_no_signal():
    st=Strikes(712.61,709,716,_ts("2026-04-29").date())
    s=build_options_cockpit_state(st)
    assert s.selected_trade_quote is None and 'Mock' in s.warning
    cs=TradeSignal('1','CALL','CONFIRMED','UD',0,_ts("2026-04-29T10:00:00"),0,0,0,0,_ts("2026-04-29T11:00:00"),0,0,None,float('nan'),0,0,0,'','')
    ps=TradeSignal('2','PUT','CONFIRMED','UA',0,_ts("2026-04-29T10:00:00"),0,0,0,0,_ts("2026-04-29T11:00:00"),0,0,None,float('nan'),0,0,0,'','')
    assert build_options_cockpit_state(st, latest_signal=cs).selected_trade_quote.option_type=='CALL'
    assert build_options_cockpit_state(st, latest_signal=ps).selected_trade_quote.option_type=='PUT'


def test_live_provider_state_label_and_warning():
    class LiveProvider:
        provider_name = "TASTYTRADE"

        def get_selected_quotes(self, underlying_price, expiration_date, call_strike, put_strike):
            base = {
                "underlying": "SPY",
                "expiration": expiration_date,
                "bid": 1.0,
                "ask": 1.2,
                "mark": 1.1,
                "spread": 0.2,
                "gamma": 0.05,
                "theta": -0.1,
                "vega": 0.03,
                "iv": 0.25,
                "provider": "TASTYTRADE_LIVE",
                "timestamp": _ts("2026-04-29T10:00:00"),
                "warning": None,
            }
            return {
                "CALL": {"symbol": "SPY_CALL", "strike": call_strike, "option_type": "CALL", "delta": 0.5, **base},
                "PUT": {"symbol": "SPY_PUT", "strike": put_strike, "option_type": "PUT", "delta": -0.5, **base},
                "warning": None,
            }

    st=Strikes(712.61,709,716,_ts("2026-04-29").date())
    sig=TradeSignal('1','CALL','CONFIRMED','UD',0,_ts("2026-04-29T10:00:00"),0,0,0,0,_ts("2026-04-29T11:00:00"),0,0,None,float('nan'),0,0,0,'','')
    state=build_options_cockpit_state(st, latest_signal=sig, provider=LiveProvider())
    assert state.provider == "TASTYTRADE_LIVE"
    assert state.selected_trade_quote.provider == "TASTYTRADE_LIVE"
    assert state.warning is None


def test_scenarios_and_projection_behaviors():
    q=MockOptionProvider().get_selected_quotes(712.61,_ts("2026-04-29").date(),709,716)['call']
    sc=simulate_option_scenarios(q)
    assert sc[0].estimated_pnl_per_contract == round((sc[0].estimated_mark-sc[0].current_mark)*100,2)

    lines=_lines(); entry=lines[1]; target=lines[0]
    proj=project_option_entry_to_target(q,712.61,entry,target,_ts("2026-04-29T09:00:00"),_ts("2026-04-29T09:00:00"))
    assert proj.estimated_entry_mark < q.mark
    assert proj.estimated_target_mark > proj.estimated_entry_mark


def test_put_entry_target_and_floor_and_missing_target_and_helpers():
    q=MockOptionProvider().get_selected_quotes(712.61,_ts("2026-04-29").date(),709,716)['put']
    lines=_lines(); entry=lines[2]; target=lines[3]
    proj=project_option_entry_to_target(q,712.61,entry,target,_ts("2026-04-29T09:00:00"),_ts("2026-04-29T09:00:00"))
    assert proj.estimated_entry_mark < q.mark and proj.estimated_target_mark > proj.estimated_entry_mark
    tiny=project_option_entry_to_target(q,800,entry,target,_ts("2026-04-29T09:00:00"),_ts("2026-04-29T09:00:00"))
    assert tiny.estimated_entry_mark >= 0.01
    miss=project_option_entry_to_target(q,712.61,entry,None,_ts("2026-04-29T09:00:00"),None)
    assert miss.warning is not None
    assert get_default_projection_time(_ts("2026-04-29T12:00:00")).hour==9
    e,t=resolve_entry_target_lines(lines, latest_signal=TradeSignal('x','CALL','CONFIRMED','UD',0,_ts("2026-04-29T10:00:00"),0,0,0,0,_ts("2026-04-29T11:00:00"),0,0,'UA',0,0,0,0,'',''), option_type='CALL', current_dt=_ts("2026-04-29T12:00:00"))
    assert e.name=='UD' and t.name=='UA'
