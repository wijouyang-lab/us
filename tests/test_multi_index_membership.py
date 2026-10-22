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
