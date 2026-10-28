from __future__ import annotations

import unittest

from tools.research.pit_recovery_gate import evaluate_gates


def passing_snapshot() -> dict:
    return {
        "member_sessions_expected": 1_000,
        "member_sessions_observed": 980,
        "ticker_total": 100,
        "tickers_at_least_90pct_coverage": 98,
        "missing_historical_tickers_total": 50,
        "missing_historical_tickers_with_verified_identity_and_ohlcv": 49,
        "independent_ohlcv_source_verified": True,
        "max_abs_close_difference_pct": 0.4,
        "unexplained_corporate_action_breaks": 0,
        "pit_availability_audit_passed": True,
        "independent_nonoverlapping_oos_windows": 12,
        "benchmark_adjusted_net_alpha_ci_lower": 0.001,
    }


class TestPitRecoveryGate(unittest.TestCase):
    def test_passing_snapshot_is_eligible_for_research_only(self) -> None:
        result = evaluate_gates(passing_snapshot())
        self.assertTrue(result["eligible_to_resume_full_history_pit_research"])
        self.assertTrue(all(gate["passed"] for gate in result["gates"].values()))
        self.assertIn("does not authorize production deployment", result["note"])

    def test_current_reported_coverage_fails_closed(self) -> None:
        snapshot = passing_snapshot()
        snapshot.update({
            "member_sessions_expected": 1_278_758,
            "member_sessions_observed": 1_171_451,
            "ticker_total": 704,
            "tickers_at_least_90pct_coverage": 593,
            "missing_historical_tickers_total": 98,
            "missing_historical_tickers_with_verified_identity_and_ohlcv": 0,
            "independent_ohlcv_source_verified": False,
            "max_abs_close_difference_pct": None,
            "unexplained_corporate_action_breaks": None,
            "pit_availability_audit_passed": False,
            "independent_nonoverlapping_oos_windows": 9,
            "benchmark_adjusted_net_alpha_ci_lower": None,
        })
        result = evaluate_gates(snapshot)
        self.assertFalse(result["eligible_to_resume_full_history_pit_research"])
        self.assertFalse(result["gates"]["member_session_coverage_ge_95pct"]["passed"])
        self.assertFalse(result["gates"]["independent_ohlcv_source_verified"]["passed"])
        self.assertFalse(result["gates"]["at_least_12_independent_oos_windows"]["passed"])

    def test_missing_independent_source_and_alpha_evidence_fail(self) -> None:
        snapshot = passing_snapshot()
        snapshot["independent_ohlcv_source_verified"] = None
        snapshot["benchmark_adjusted_net_alpha_ci_lower"] = None
        result = evaluate_gates(snapshot)
        self.assertFalse(result["gates"]["independent_ohlcv_source_verified"]["passed"])
        self.assertFalse(result["gates"]["benchmark_adjusted_net_alpha_ci_lower_gt_zero"]["passed"])
        self.assertFalse(result["eligible_to_resume_full_history_pit_research"])

    def test_inconsistent_counts_are_rejected(self) -> None:
        snapshot = passing_snapshot()
        snapshot["member_sessions_observed"] = 1_001
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            evaluate_gates(snapshot)


if __name__ == "__main__":
    unittest.main()
