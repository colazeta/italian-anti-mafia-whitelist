"""Synthetic-only regression tests; never query external data or production DB."""
from __future__ import annotations
import importlib.util
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


source = load('research_source_pilot', BASE / 'scripts/run_source_pilot.py')
ledger = load('research_eligibility', BASE / 'scripts/build_eligibility.py')


class SourceDiagnosticTests(unittest.TestCase):
    def make(self, **changes):
        row = {'identifiers': ['12345678901'], 'name': 'SYNTHETIC COMPANY',
               'application_date': '2026-01-01', 'source_status': 'pending'}
        row.update(changes)
        return source.normalise(row, {'source_key': 'synthetic', 'reference_date': '2026-07-01'})

    def test_empty_is_not_zero_duration(self):
        self.assertIsNone(source.quantiles([])['median_days'])

    def test_invalid_calendar_date_stays_unknown(self):
        self.assertIsNone(source.parse_date('31/02/2026'))

    def test_future_application_excluded(self):
        result = source.analyse([self.make(application_date='2027-01-01')])
        self.assertEqual(result['observed_pending_age']['n'], 0)
        self.assertEqual(result['date_exclusions']['application_after_reference'], 1)

    def test_earlier_listing_not_duration(self):
        result = source.analyse([self.make(source_status='listed', observed_listing_date='2025-01-01')])
        self.assertEqual(result['candidate_application_to_listing_lag_NOT_processing_time']['n'], 0)
        self.assertEqual(result['date_exclusions']['listing_precedes_application'], 1)

    def test_future_listing_not_duration(self):
        result = source.analyse([self.make(source_status='listed', observed_listing_date='2027-01-01')])
        self.assertEqual(result['candidate_application_to_listing_lag_NOT_processing_time']['n'], 0)

    def test_pending_age_not_completed_time(self):
        result = source.analyse([self.make()])
        self.assertEqual(result['observed_pending_age']['median_days'], 181)
        self.assertIsNone(result['true_processing_time'])

    def test_renewals_not_mixed_with_pending_initial_population(self):
        result = source.analyse([self.make(source_status='renewal_update_in_progress')])
        self.assertEqual(result['observed_pending_age']['n'], 0)
        self.assertEqual(result['renewal_date_age_diagnostic']['n'], 1)

    def test_duplicate_candidate_episode_excluded(self):
        row = self.make()
        self.assertEqual(source.safe_records([row, row])[0], [])

    def test_conflicting_names_for_id_excluded(self):
        rows = [self.make(), self.make(name='DIFFERENT SYNTHETIC COMPANY')]
        self.assertEqual(source.safe_records(rows)[0], [])

    def test_multiple_identifiers_not_arbitrarily_chosen(self):
        self.assertEqual(source.safe_records([self.make(identifiers=['12345678901', '22345678901'])])[0], [])

    def test_multiple_dates_not_collapsed_to_min(self):
        row = self.make(application_date='', application_dates=['2026-01-01', '2026-02-01'])
        self.assertEqual(row['app_count'], 2)
        self.assertIsNone(row['app'])

    def test_parenthesised_date_not_promoted(self):
        row = self.make(application_date='', application_dates=[{'date': '01/01/2026', 'parenthesized': True}])
        self.assertIsNone(row['app'])

    def test_source_approved_pair_remains_only_proxy(self):
        result = source.analyse([self.make(source_status='listed', observed_listing_date='2026-02-01')])
        self.assertEqual(result['candidate_application_to_listing_lag_NOT_processing_time']['median_days'], 31)
        self.assertIsNone(result['true_processing_time'])

    def test_missing_terminal_outcomes_blocks_clearance(self):
        result = source.analyse([self.make()])
        self.assertIsNone(result['clearance_rate'])
        self.assertIsNone(result['backlog_rate'])

    def test_disappearance_is_not_resolution(self):
        result = source.transition_diagnostics([('2026-01-01', [self.make()]), ('2026-02-01', [])])[0]
        self.assertEqual(result['disappeared_from_source_NOT_resolved'], 1)
        self.assertIsNone(result['administrative_decision_intervals'])

    def test_published_transition_is_not_administrative_interval(self):
        result = source.transition_diagnostics([('2026-01-01', [self.make()]),
                    ('2026-02-01', [self.make(source_status='listed')])])[0]
        self.assertEqual(result['observed_transitions']['pending -> listed'], 1)
        self.assertIsNone(result['administrative_decision_intervals'])

    def test_quantile_definition(self):
        self.assertEqual(source.quantiles([10, 20])['median_days'], 15)
        self.assertEqual(source.quantiles([10, 20])['p90_days'], 19)

    def test_strict_age_threshold(self):
        self.assertEqual(source.quantiles([90, 91])['gt90'], 1)


class DiscoveryLedgerTests(unittest.TestCase):
    def test_cross_regime_populations_do_not_make_complete_scope(self):
        rows = ledger.assess([{'authority_key': 'synthetic'}], [
            {'authority_key': 'synthetic', 'regime_code': ledger.ORDINARY, 'population_scope': 'listed'},
            {'authority_key': 'synthetic', 'regime_code': 'SPECIAL', 'population_scope': 'applicant'}], [])
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(x['both_populations_discovered'] == 'unresolved' for x in rows))

    def test_combined_source_counts_as_both_logical_populations(self):
        rows = ledger.assess([{'authority_key': 'synthetic'}], [
            {'authority_key': 'synthetic', 'regime_code': ledger.ORDINARY,
             'population_scope': 'listed_and_applicant'}], [])
        self.assertEqual(rows[0]['both_populations_discovered'], 'yes')
        self.assertTrue(rows[0]['clearance_rate_eligibility'].startswith('not_verified'))

    def test_absence_from_registry_is_unresolved(self):
        rows = ledger.assess([{'authority_key': 'synthetic'}], [], [])
        self.assertEqual(rows[0]['applicant_discovered'], 'unresolved')

    def test_duplicate_authority_rejected(self):
        with self.assertRaises(ValueError):
            ledger.assess([{'authority_key': 'synthetic'}] * 2, [], [])

    def test_orphan_series_rejected(self):
        with self.assertRaises(ValueError):
            ledger.assess([], [{'authority_key': 'synthetic', 'regime_code': ledger.ORDINARY}], [])

    def test_output_deterministic(self):
        rows = ledger.assess([{'authority_key': 'synthetic'}], [], [])
        self.assertEqual(ledger.render(rows), ledger.render(rows))
        self.assertNotIn('\r', ledger.render(rows))


if __name__ == '__main__':
    unittest.main()
