from app import fmt_price, fmt_nan, safe_to_dict, render_badge


def test_fmt_helpers():
    assert fmt_price(1.234) == '1.23'
    assert fmt_nan(float('nan')) == '-'


def test_safe_to_dict_redacts():
    d = safe_to_dict({'access_token':'abc','x':1})
    assert d['access_token'] == '[REDACTED]'


def test_render_badge_markup():
    m = render_badge('CALL','call')
    assert 'badge-call' in m and 'CALL' in m
