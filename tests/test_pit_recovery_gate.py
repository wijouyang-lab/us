from __future__ import annotations

import unittest

from tools.research.pit_recovery_gate import evaluate_gates


def data_snapshot() -> dict:
    return {
        "member_sessions_expected": 1_000,
        "member_sessions_observed": 980,
        "ticker_total": 100,
        "tickers_at_least_90pct_coverage": 98,
        "missing_historical_tickers_total": 50,
        "missing_historical_tickers_with_verified_identity_and_ohlcv": 49,
        "independent_ohlcv_source_verified": True,
        "max_abs_close_difference_pct": 0.5,
        "unexplained_corporate_action_breaks": 0,
        "pit_availability_audit_passed": True,
    }


def strategy_snapshot() -> dict:
    snapshot = data_snapshot()
    snapshot.update({
        "independent_nonoverlapping_oos_windows": 12,
        "benchmark_adjusted_net_alpha_ci_lower": 0.001,
        "max_drawdown_pct": 20.0,
        "robustness_checks_passed": True,
    })
    return snapshot


def production_snapshot() -> dict:
    snapshot = strategy_snapshot()
    snapshot.update({
        "risk_controls_verified": True,
        "production_regression_tests_passed": True,
        "paper_trading_days": 40,
        "human_review_approved": True,
    })
    return snapshot


class TestPitRecoveryGate(unittest.TestCase):
    def test_data_gate_does_not_require_strategy_evidence(self) -> None:
        result = evaluate_gates(data_snapshot())
        self.assertTrue(result["stages"]["data_research"]["ready"])
        self.assertTrue(result["eligible_to_resume_full_history_pit_research"])
        self.assertFalse(result["stages"]["strategy_validation"]["ready"])
        self.assertFalse(result["strategy_validation_ready"])
        self.assertFalse(result["stages"]["production_deployment"]["ready"])

    def test_current_reported_coverage_fails_all_stages(self) -> None:
        snapshot = data_snapshot()
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
        })
        result = evaluate_gates(snapshot)
        self.assertFalse(result["stages"]["data_research"]["ready"])
        self.assertFalse(result["strategy_validation_ready"])
        self.assertFalse(result["production_deployment_ready"])
        gates = result["stages"]["data_research"]["gates"]
        self.assertFalse(gates["member_session_coverage_ge_95pct"]["passed"])
        self.assertFalse(gates["independent_ohlcv_source_verified"]["passed"])

    def test_strategy_can_pass_only_after_data_and_needs_robustness(self) -> None:
        result = evaluate_gates(strategy_snapshot())
        self.assertTrue(result["stages"]["data_research"]["ready"])
        self.assertTrue(result["strategy_validation_ready"])
        self.assertFalse(result["production_deployment_ready"])
        snapshot = strategy_snapshot()
        snapshot["robustness_checks_passed"] = False
        self.assertFalse(evaluate_gates(snapshot)["strategy_validation_ready"])

    def test_production_requires_all_separate_controls(self) -> None:
        result = evaluate_gates(production_snapshot())
        self.assertTrue(result["production_deployment_ready"])
        for key in ("risk_controls_verified", "production_regression_tests_passed",
                    "paper_trading_days", "human_review_approved"):
            snapshot = production_snapshot()
            snapshot.pop(key)
            self.assertFalse(evaluate_gates(snapshot)["production_deployment_ready"])

    def test_boundary_values_pass(self) -> None:
        result = evaluate_gates(production_snapshot())
        self.assertTrue(result["production_deployment_ready"])

    def test_missing_data_evidence_fails_closed(self) -> None:
        snapshot = data_snapshot()
        snapshot["independent_ohlcv_source_verified"] = None
        snapshot["max_abs_close_difference_pct"] = None
        result = evaluate_gates(snapshot)
        self.assertFalse(result["stages"]["data_research"]["ready"])
        self.assertFalse(result["eligible_to_resume_full_history_pit_research"])

    def test_inconsistent_counts_are_rejected(self) -> None:
        snapshot = data_snapshot()
        snapshot["member_sessions_observed"] = 1_001
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            evaluate_gates(snapshot)


if __name__ == "__main__":
    unittest.main()
