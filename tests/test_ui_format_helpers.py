from app import display_line_description, display_line_list, display_line_name, fmt_price, fmt_nan, safe_to_dict, render_badge


def test_fmt_helpers():
    assert fmt_price(1.234) == '1.23'
    assert fmt_nan(float('nan')) == '-'


def test_safe_to_dict_redacts():
    d = safe_to_dict({'access_token':'abc','x':1})
    assert d['access_token'] == '[REDACTED]'


def test_render_badge_markup():
    m = render_badge('CALL','call')
    assert 'badge-call' in m and 'CALL' in m


def test_display_line_names_are_product_facing():
    assert display_line_name("UA") == "Upper Put Trigger"
    assert display_line_name("UD") == "Upper Call Trigger"
    assert display_line_description("LA") == "PUT watch from the prior-session low"
    assert display_line_list(["UD", "UA"]) == "Upper Call Trigger, Upper Put Trigger"
