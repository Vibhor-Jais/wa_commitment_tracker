from wa_commitment_tracker.parser import parse_message, is_commitment_message, normalize_amount

SAMPLE_1 = """Good morning Team,

CA noa:- 
SA noa:- 1
SA Affluent -1
Elite:- 
M0 Value:-1L
Ca value:- 
Sa value:- 5 L 
RTD:- 5L
RD:- 
LI:- 1L
HI:- 
MF:-
SIP:- 2
PMJDY:-
APY:- 
PMJJBY:- 
PMSBY:-"""

SAMPLE_4 = """Good morning Team,

CA noa:- 
SA noa:- 1
SA Affluent -
Elite:- 
M0 Value: 11k
Ca value:- 
Sa value:-3L
RTD:- 3L
RD:- 
LI:- 
HI:- 
MF:-
SIP:- 1
PMJDY:-
APY:- 
PMJJBY:- 
PMSBY:-"""

BLANK_TEMPLATE = """Good morning Team,

CA noa:- 
SA noa:- 
SA Affluent -
Elite:- 
M0 Value:- 
Ca value:- 
Sa value:- 
RTD:- 
RD:- 
LI:- 
HI:- 
MF:-
SIP:- 
PMJDY:-
APY:- 
PMJJBY:- 
PMSBY:-"""


def test_normalize_amount():
    assert normalize_amount("1L") == 100_000
    assert normalize_amount("5 L") == 500_000
    assert normalize_amount("5 lakh") == 500_000
    assert normalize_amount("11k") == 11_000
    assert normalize_amount("25,000") == 25_000
    assert normalize_amount("2") == 2
    assert normalize_amount("") is None
    assert normalize_amount("-") is None


def test_parse_sample_1():
    parsed, unparsed = parse_message(SAMPLE_1)
    assert unparsed == []
    assert parsed["SA noa"] == 1
    assert parsed["SA Affluent"] == 1
    assert parsed["M0 Value"] == 100_000
    assert parsed["SA value"] == 500_000
    assert parsed["RTD"] == 500_000
    assert parsed["LI"] == 100_000
    assert parsed["SIP"] == 2
    # unmentioned/blank fields must stay None - no cross-field defaulting
    assert parsed["CA value"] is None
    assert parsed["Elite"] is None
    assert parsed["PMJDY"] is None


def test_parse_sample_4_mixed_units():
    parsed, unparsed = parse_message(SAMPLE_4)
    assert unparsed == []
    assert parsed["M0 Value"] == 11_000  # 'k' suffix
    assert parsed["SA value"] == 300_000  # 'L' suffix, no space
    assert parsed["RTD"] == 300_000
    assert parsed["SIP"] == 1
    assert parsed["LI"] is None


def test_blank_template_is_not_a_commitment():
    assert is_commitment_message(BLANK_TEMPLATE) is False


def test_sample_1_is_a_commitment():
    assert is_commitment_message(SAMPLE_1) is True


def test_lac_and_lacs_are_lakh_synonyms():
    assert normalize_amount("3 lac") == 300_000
    assert normalize_amount("7 lakhs") == 700_000
    assert normalize_amount("2 lacs") == 200_000
    assert normalize_amount("5lac") == 500_000


def test_trailing_noise_after_a_valid_number_is_ignored():
    assert normalize_amount("1 noa") == 1
    assert normalize_amount("1/0") == 1
    assert normalize_amount("2/2") == 2
    assert normalize_amount("1-") == 1
    assert normalize_amount("1 <This message was edited>") == 1
