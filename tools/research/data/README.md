Third-party research data vendored for reproducible point-in-time universe filtering.

Source: https://github.com/lawcal/sp500-components-history/blob/2d0556e4ca01dc9203231c8b60d503a227be4512/data/components_history.csv
Source commit: 2d0556e4ca01dc9203231c8b60d503a227be4512 (2026-10-14)
Source blob SHA: c025e09a6bbb2e12310a3f9fcef9114a0b59df90
Original fields include symbol, date_added, date_removed, and created_at. Asterisk-marked effective dates are approximations in the upstream source and are preserved in the CSV; consumers strip the asterisk for date comparisons and record this limitation.

Coverage/limitations documented by the upstream project: https://github.com/lawcal/sp500-components-history/tree/2d0556e4ca01dc9203231c8b60d503a227be4512#data-source-caveats
The source tracks symbols since 2007-03-05 and uses Wikipedia revision history. Ticker transitions are treated as separate symbols and some effective dates are approximated. This is a research reference, not authoritative S&P Global constituent history. The research pipeline must report price/constituent coverage and must not claim zero survivorship bias.

The upstream source is distributed under the MIT License. The license text is included as LICENSE.sp500-components-history.txt.


## Same-security ticker aliases

`sp500_ticker_aliases.csv` maps former symbols to a canonical current symbol only when the historical membership row has the exact registered SEC CIK. The registry stores HTTPS issuer/filing references and change notes. This recovers price history where Yahoo retains the same security under its current ticker (for example, same-issuer name/ticker changes), and avoids mixing in a different security where a ticker was later reused (for example, ARNC is CIK-guarded).

Aliases do not map an acquired company into an acquirer, do not infer ticker mappings from name similarity, and do not merge different CIKs. CIK equality is a guard against symbol reuse, not proof that corporate-action-adjusted price history is economically seamless; all merged price inputs still pass the coverage gates. Source-date asterisks remain approximate. Review the issuer reference and CIK before adding or changing an alias.

The research price-refresh audit records the alias file's Git blob SHA, the applied old-to-canonical symbol mapping, and canonical ticker counts so the universe transformation is reproducible.
