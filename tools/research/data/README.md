Third-party research data vendored for reproducible point-in-time universe filtering.

Source: https://github.com/lawcal/sp500-components-history/blob/c025e09a6bbb2e12310a3f9fcef9114a0b59df90/data/components_history.csv
Source commit: c025e09a6bbb2e12310a3f9fcef9114a0b59df90
Source blob SHA: c025e09a6bbb2e12310a3f9fcef9114a0b59df90
Original fields include symbol, date_added, date_removed, and created_at. Asterisk-marked effective dates are approximations in the upstream source and are preserved in the CSV; consumers strip the asterisk for date comparisons and record this limitation.

Coverage/limitations documented by the upstream project: https://github.com/lawcal/sp500-components-history/tree/c025e09a6bbb2e12310a3f9fcef9114a0b59df90#data-source-caveats
The source tracks symbols since 2007-03-05 and uses Wikipedia revision history. Ticker transitions are treated as separate symbols and some effective dates are approximated. This is a research reference, not authoritative S&P Global constituent history. The research pipeline must report price/constituent coverage and must not claim zero survivorship bias.

The upstream source is distributed under the MIT License. The license text is included as LICENSE.sp500-components-history.txt.
