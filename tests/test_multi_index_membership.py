from pathlib import Path

from tools.research.multi_index_membership import load_multi_index_membership


def test_combines_sp500_nasdaq_and_dow_membership_without_duplicate_ticker_keys(tmp_path: Path):
    sp500 = tmp_path / "sp500.csv"
    aliases = tmp_path / "aliases.csv"
    nasdaq = tmp_path / "nasdaq.csv"
    dow = tmp_path / "dow.csv"

    sp500.write_text(
        "symbol,cik,name,sector,date_added,date_removed,created_at\n"
        "AAA,1,AAA Inc.,technology,2020-01-02,,2020-01-02\n",
        encoding="utf-8",
    )
    aliases.write_text(
        "old_ticker,canonical_ticker,cik,source_url,change_type\n",
        encoding="utf-8",
    )
    nasdaq.write_text(
        "symbol,name,opt-in,opt-out\n"
        "AAA,AAA Inc.,2021-01-04,2022-01-03\n"
        "BBB,BBB Inc.,2021-01-04,\n",
        encoding="utf-8",
    )
    dow.write_text(
        "symbol,name,opt-in,opt-out\n"
        "CCC,CCC Inc.,2019-01-02,\n",
        encoding="utf-8",
    )

    history = load_multi_index_membership(sp500, aliases, nasdaq, dow)

    assert set(history) == {"AAA", "BBB", "CCC"}
    assert len(history["AAA"]) == 2
    assert history["AAA"][0].date_added.isoformat() == "2020-01-02"
    assert history["AAA"][1].date_removed.isoformat() == "2022-01-03"
    assert history["BBB"][0].date_removed is None
    assert history["CCC"][0].date_added.isoformat() == "2019-01-02"



def test_applies_cik_grounded_alias_to_other_indices_only_during_known_issuer_interval(tmp_path: Path):
    sp500 = tmp_path / "sp500.csv"
    aliases = tmp_path / "aliases.csv"
    nasdaq = tmp_path / "nasdaq.csv"
    dow = tmp_path / "dow.csv"

    sp500.write_text(
        "symbol,cik,name,sector,date_added,date_removed,created_at\n"
        "OLD,123,Old Corp.,technology,2018-01-02,2021-01-04,2018-01-02\n",
        encoding="utf-8",
    )
    aliases.write_text(
        "old_ticker,canonical_ticker,cik,source_url,change_type\n"
        "OLD,NEW,123,https://example.com/issuer-ticker-change,same issuer ticker change\n",
        encoding="utf-8",
    )
    nasdaq.write_text(
        "symbol,name,opt-in,opt-out\n"
        "OLD,Old Corp.,2019-01-02,2022-01-03\n",
        encoding="utf-8",
    )
    dow.write_text("symbol,name,opt-in,opt-out\n", encoding="utf-8")

    history = load_multi_index_membership(sp500, aliases, nasdaq, dow)

    # The historical ticker is canonicalized only while the S&P source grounds
    # OLD to the same CIK; the later interval is kept under OLD to avoid rewriting
    # a potentially reused ticker.
    assert any(
        item.date_added.isoformat() == "2019-01-02"
        and item.date_removed.isoformat() == "2021-01-04"
        for item in history["NEW"]
    )
    assert any(
        item.date_added.isoformat() == "2021-01-04"
        and item.date_removed.isoformat() == "2022-01-03"
        for item in history["OLD"]
    )
