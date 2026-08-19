from crisis_config import Region, infer_region
from crisis_parse import (
    build_case,
    extract_leading_score,
    extract_short_status,
    extract_year,
    parse_batch_file,
    parse_case_block,
    parse_onlyne_relevance,
    split_cases,
)

BOLD_STYLE_CASE = """
## Case 001

**Company:** Satyam Computer Services
**Industry:** IT Services
**Year:** 2009
**Crisis Type:** Accounting Fraud / Corporate Governance Collapse

**Trigger Event:** Founder-chairman confessed to inflating profits for years.

**Response Type:** Reactive

**Response Speed Score:** 2
*Explanatory italic sentence about the score goes here, spanning more detail.*

**Transparency Score:** 2
*Another explanatory sentence.*

**Legal / Regulatory Framework Triggered:** SEBI investigation and penalties.

**Resolution Status:** Resolved (company survived via acquisition)

**What Went Right:**
- Government intervened within days.
- Transparent bidding process for the sale.

**What Went Wrong:**
- Fraud went undetected for 7 years.

**Best Practice / What Should Have Happened:** Independent directors should have insisted on a forensic audit.

**Estimated Impact:**
Financial: ₹7,800 crore fraud.

**Onlyne Relevance:** ORM / Crisis Comms / Legal Takedown (retrospective note)

**Key Sources:**
- SEC.gov litigation release
"""

PLAIN_STYLE_CASE = """
Case 13
Company: Credit Suisse
Industry: Banking / Financial Services
Year: 2021 (Archegos + Greensill)
Crisis Type: Risk management failure

Trigger Event: Collapse of two clients within weeks of each other.
Response Type: Reactive
Response Speed Score: 2
Transparency Score: 2
Legal/Regulatory Framework Triggered: FINMA enforcement action
Resolution Status: Fatal — the bank never recovered
What Went Right: Commissioned an independent external investigation.
What Went Wrong: Ignored internal risk warnings for months.
Best Practice / What Should Have Happened: Concentration-risk limits needed hard caps.
Estimated Impact: ~$5.5B direct trading loss.
Onlyne Relevance: Crisis Comms / Reputational trust erosion pattern
Key Sources: finews.com, Morningstar
"""

CASE_ID_STYLE_CASE = """
Case ID: 30
Company: Exxon Corporation
Industry: Oil & gas
Year: 1989
Crisis Type: Environmental disaster

Trigger Event: Tanker struck a reef, spilling crude oil.
Response Type: Denial-Silence, then Delayed
Response Speed Score: 1
Transparency Score: 2
Legal/Regulatory Framework Triggered: Clean Water Act
Resolution Status: Partially Resolved
What Went Right: Scaled up cleanup resources by summer.
What Went Wrong: Initial silence for days after the spill.
Best Practice / What Should Have Happened: Immediate public acknowledgement.
Estimated Impact: Multi-billion dollar cleanup and legal costs.
Onlyne Relevance: Crisis Comms / ORM
Key Sources: EPA archives
"""


def test_split_cases_handles_all_heading_variants():
    text = BOLD_STYLE_CASE + "\n---\n" + PLAIN_STYLE_CASE + "\n---\n" + CASE_ID_STYLE_CASE
    cases = split_cases(text)
    assert [n for n, _ in cases] == [1, 13, 30]


def test_split_cases_case_dash_heading():
    text = "## CASE-001\n\n**Company:** Johnson & Johnson\n"
    cases = split_cases(text)
    assert cases[0][0] == 1


def test_split_cases_heading_with_trailing_title():
    text = "## Case 17: Fortis Healthcare — Singh Brothers Fund Diversion\n\n**Company:** Fortis\n"
    cases = split_cases(text)
    assert cases[0][0] == 17


def test_parse_case_block_bold_style_extracts_all_fields():
    _, block = split_cases(BOLD_STYLE_CASE)[0]
    fields = parse_case_block(block)
    assert fields["company"] == "Satyam Computer Services"
    assert fields["year"] == "2009"
    assert "Founder-chairman" in fields["trigger_event"]
    # The italic explanatory sentence stays attached to the score field's raw value.
    assert "Explanatory italic sentence" in fields["response_speed_score"]


def test_parse_case_block_plain_style_extracts_all_fields():
    _, block = split_cases(PLAIN_STYLE_CASE)[0]
    fields = parse_case_block(block)
    assert fields["company"] == "Credit Suisse"
    assert fields["legal_framework"] == "FINMA enforcement action"
    assert fields["resolution_status"].startswith("Fatal")


def test_extract_year_from_range_and_plain():
    assert extract_year("2009") == 2009
    assert extract_year("2006–2008 (scandal broke Nov 2006)") == 2006
    assert extract_year("no year mentioned") is None


def test_extract_leading_score_handles_slash_and_plain():
    assert extract_leading_score("2") == 2
    assert extract_leading_score("2/5 — some explanation") == 2
    assert extract_leading_score("no digit here") is None


def test_extract_short_status_takes_first_nonempty_line():
    assert extract_short_status("Resolved\n*A longer italic explanation.*") == "Resolved"
    assert extract_short_status("Fatal — the bank never recovered") == "Fatal — the bank never recovered"


def test_parse_onlyne_relevance_splits_on_slash():
    tags = parse_onlyne_relevance("ORM / Crisis Comms / Legal Takedown (retrospective note)")
    assert tags == ["ORM", "Crisis Comms", "Legal Takedown (retrospective note)"]


def test_build_case_success():
    _, block = split_cases(BOLD_STYLE_CASE)[0]
    case, errors = build_case(1, block, Region.INDIA, "sample.md")
    assert errors == []
    assert case.case_id == "india_case_001"
    assert case.year == 2009
    assert case.response_speed_score == 2
    assert case.onlyne_relevance == ["ORM", "Crisis Comms", "Legal Takedown (retrospective note)"]


def test_build_case_missing_field_logs_error_and_returns_none():
    block = "\n**Company:** Acme Corp\n**Industry:** Widgets\n"  # missing everything else
    case, errors = build_case(2, block, Region.EUROPE, "sample.md")
    assert case is None
    assert len(errors) > 0
    assert all(e.case_id == "europe_case_002" for e in errors)
    missing_fields = {e.missing_field for e in errors}
    assert "trigger_event" in missing_fields


def test_parse_batch_file_end_to_end():
    text = BOLD_STYLE_CASE + "\n---\n" + PLAIN_STYLE_CASE
    cases, errors = parse_batch_file(text, Region.INDIA, "sample.md")
    assert len(cases) == 2
    assert errors == []
    assert {c.case_id for c in cases} == {"india_case_001", "india_case_013"}


def test_infer_region_keywords():
    assert infer_region("india-corporate-crisis-case-studies-batch1.md") == Region.INDIA
    assert infer_region("European_Crisis_Case_Studies.md") == Region.EUROPE
    assert infer_region("us-case-30-32.md") == Region.AMERICA
    assert infer_region("crisis-case-studies-batch2-us.md") == Region.AMERICA


def test_infer_region_filename_overrides():
    assert infer_region("crisis-case-studies-batch1.md") == Region.AMERICA
    assert infer_region("crisis-case-studies-batch2.md") == Region.AMERICA


def test_infer_region_unknown_returns_none():
    assert infer_region("mystery-cases.md") is None
