from tools.research.pit_sec_edgar import (
    parse_sec_acceptance_datetime,
    parse_sec_submissions,
)


def test_parse_sec_does_not_treat_raw_acceptance_datetime_as_verified_utc():
    payload = {
        "name": "Example Corp",
        "filings": {
            "recent": {
                "accessionNumber": ["0000123456-26-000001", "0000123456-26-000002"],
                "form": ["10-Q", "8-K"],
                "filingDate": ["2026-10-22", "2026-10-22"],
                "acceptanceDateTime": ["2026-10-22T15:30:00Z", "2026-10-22T16:30:00Z"],
                "primaryDocument": ["quarter.htm", "current.htm"],
                "items": ["", "2.02, 9.01"],
            }
        },
    }
    records = parse_sec_submissions(
        payload, first_seen_at_utc="2026-10-22T17:00:00Z", ticker="EXM",
    )
    assert len(records) == 2
    assert records[0]["published_at_utc"] is None
    assert records[0]["availability_status"] == "timestamp_missing"
    assert records[0]["publication_timestamp_status"] == "header_missing"
    assert records[0]["event_type"] == "earnings"
    assert records[1]["published_at_utc"] is None
    assert records[1]["availability_status"] == "timestamp_missing"
    assert records[1]["event_type"] == "earnings"
    assert records[0]["tickers"] == ["EXM"]


def test_parse_sec_uses_separately_supplied_sgml_header_time_as_new_york_time():
    payload = {
        "name": "Example Corp",
        "filings": {
            "recent": {
                "accessionNumber": ["0000123456-26-000004"],
                "form": ["8-K"],
                "acceptanceDateTime": ["2026-10-22T16:30:00Z"],
                "primaryDocument": ["current.htm"],
                "items": ["2.02"],
            }
        },
    }
    headers = {
        "000012345626000004": "<SEC-DOCUMENT>\n<ACCEPTANCE-DATETIME>20261022093000\nACCESSION NUMBER: 0000123456-26-000004\n",
    }
    record = parse_sec_submissions(
        payload,
        first_seen_at_utc="2026-10-22T13:31:00Z",
        ticker="EXM",
        submission_headers_by_accession=headers,
    )[0]
    assert record["published_at_utc"] == "2026-10-22T14:30:00Z"
    assert record["availability_status"] == "available"
    assert record["publication_timestamp_source"] == "sec_sgml_acceptance_datetime"
    assert record["publication_timestamp_status"] == "verified_from_sgml_header"
    assert record["event_type"] == "earnings"


def test_parse_sec_does_not_treat_filing_date_as_publication_time():
    payload = {
        "name": "Example Corp",
        "filings": {
            "recent": {
                "accessionNumber": ["0000123456-26-000003"],
                "form": ["8-K"],
                "filingDate": ["2026-10-22"],
                "primaryDocument": ["current.htm"],
                "items": ["5.02"],
            }
        },
    }
    record = parse_sec_submissions(
        payload, first_seen_at_utc="2026-10-22T17:00:00Z", ticker="EXM",
    )[0]
    assert record["published_at_utc"] is None
    assert record["availability_status"] == "timestamp_missing"
    assert record["event_type"] == "company_news"


def test_parse_sec_acceptance_datetime_rejects_missing_duplicate_and_bad_header():
    assert parse_sec_acceptance_datetime(None)["status"] == "header_missing"
    assert parse_sec_acceptance_datetime("<SUBMISSION>no timestamp")["status"] == "acceptance_datetime_missing"
    duplicate = "<ACCEPTANCE-DATETIME>20261022093000\n<ACCEPTANCE-DATETIME>20261022093100"
    assert parse_sec_acceptance_datetime(duplicate)["status"] == "acceptance_datetime_ambiguous"
    wrong_accession = "ACCESSION NUMBER: 0000123456-26-000099\n<ACCEPTANCE-DATETIME>20261022093000"
    assert parse_sec_acceptance_datetime(
        wrong_accession, expected_accession="0000123456-26-000004"
    )["status"] == "accession_mismatch"
    missing_accession = "<ACCEPTANCE-DATETIME>20261022093000"
    assert parse_sec_acceptance_datetime(
        missing_accession, expected_accession="0000123456-26-000004"
    )["status"] == "accession_missing_or_ambiguous"
    invalid = "<ACCEPTANCE-DATETIME>20261342093000"
    assert parse_sec_acceptance_datetime(invalid)["status"] == "acceptance_datetime_invalid"


def test_parse_sec_acceptance_datetime_uses_fixed_est_in_summer_and_winter():
    # The SEC specification calls this field EST; do not apply a seasonal UTC-4 offset.
    winter = parse_sec_acceptance_datetime("<ACCEPTANCE-DATETIME>20261101013000")
    assert winter["published_at_utc"] == "2026-11-01T06:30:00Z"
    assert winter["status"] == "verified_from_sgml_header"

    summer = parse_sec_acceptance_datetime("<ACCEPTANCE-DATETIME>20260308023000")
    assert summer["published_at_utc"] == "2026-03-08T07:30:00Z"
    assert summer["status"] == "verified_from_sgml_header"


def test_parse_sec_handles_missing_or_malformed_payload_safely():
    assert parse_sec_submissions({}, first_seen_at_utc="2026-10-22T17:00:00Z") == []
    assert parse_sec_submissions(
        {"filings": {"recent": {"form": ["10-Q"], "accessionNumber": []}}},
        first_seen_at_utc="2026-10-22T17:00:00Z",
    ) == []
