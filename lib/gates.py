"""
Gates Module - Data Integrity & Quality Gates

Per MASTER_SPEC.md §6:
- data_integrity: All §3.4 invariants (6 queries, all must return 0)
- project_brand_required: Non-internal projects must have brand
- project_brand_consistency: Non-internal projects client_id must match brand.client_id
- project_client_populated: Non-internal projects must have client_id
- internal_project_client_null: Internal projects must have client_id = NULL
- client_coverage: ≥80% of applicable tasks
- commitment_ready: ≥50% of communications have sufficient body text
- capacity_baseline: All lanes have positive weekly_hours
- finance_ar_coverage: ≥95% of AR invoices are valid
- finance_ar_clean: All AR invoices valid
"""

import sqlite3
from pathlib import Path
from typing import Dict, Any

DB_PATH = Path(__file__).parent.parent / "data" / "state.db"


class GateEvaluator:
    """Evaluates all gates per MASTER_SPEC.md §6."""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
    
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")  # Enable FK enforcement
        return conn
    
    def _query_zero(self, sql: str) -> bool:
        """Returns True if query returns c = 0."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            row = cursor.fetchone()
            return row['c'] == 0
        finally:
            conn.close()
    
    def _query_value(self, sql: str, column: str = 'pct') -> float:
        """Returns numeric value from query."""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            row = cursor.fetchone()
            return float(row[column]) if row[column] is not None else 0.0
        finally:
            conn.close()
    
    def evaluate_all(self) -> Dict[str, Any]:
        """Evaluate all gates. Returns dict with gate names and results."""
        gates = {}
        
        # data_integrity: ALL invariants from §3.4 must pass
        gates['data_integrity'] = self._check_data_integrity()
        
        # Project gates
        gates['project_brand_required'] = self._query_zero("""
            SELECT COUNT(*) AS c FROM projects WHERE is_internal = 0 AND brand_id IS NULL
        """)
        gates['project_brand_consistency'] = self._query_zero("""
            SELECT COUNT(*) AS c FROM projects p 
            JOIN brands b ON p.brand_id = b.id 
            WHERE p.is_internal = 0 AND p.client_id != b.client_id
        """)
        gates['project_client_populated'] = self._query_zero("""
            SELECT COUNT(*) AS c FROM projects WHERE is_internal = 0 AND client_id IS NULL
        """)
        gates['internal_project_client_null'] = self._query_zero("""
            SELECT COUNT(*) AS c FROM projects WHERE is_internal = 1 AND client_id IS NOT NULL
        """)
        
        # client_coverage: ≥80% of applicable tasks
        coverage = self._query_value("""
            SELECT COALESCE(
                100.0 * SUM(CASE WHEN client_link_status = 'linked' THEN 1 ELSE 0 END) /
                NULLIF(SUM(CASE WHEN client_link_status != 'n/a' THEN 1 ELSE 0 END), 0),
                100.0
            ) AS pct FROM tasks
        """)
        gates['client_coverage'] = coverage >= 80
        gates['client_coverage_pct'] = coverage
        
        # commitment_ready: ≥50% of communications have sufficient body text
        ready = self._query_value("""
            SELECT COALESCE(
                100.0 * SUM(CASE WHEN body_text IS NOT NULL AND LENGTH(body_text) >= 50 THEN 1 ELSE 0 END) /
                NULLIF(COUNT(*), 0),
                100.0
            ) AS pct FROM communications
        """)
        gates['commitment_ready'] = ready >= 50
        gates['commitment_ready_pct'] = ready
        
        # capacity_baseline: All lanes have positive weekly_hours
        gates['capacity_baseline'] = self._query_zero("""
            SELECT COUNT(*) AS c FROM capacity_lanes WHERE weekly_hours <= 0
        """)
        
        # finance_ar_coverage: ≥95% of AR invoices are valid
        ar_coverage = self._query_value("""
            SELECT COALESCE(
                100.0 * SUM(CASE WHEN client_id IS NOT NULL AND due_date IS NOT NULL THEN 1 ELSE 0 END) /
                NULLIF(COUNT(*), 0),
                100.0
            ) AS pct 
            FROM invoices 
            WHERE status IN ('sent', 'overdue') AND paid_date IS NULL
        """)
        gates['finance_ar_coverage'] = ar_coverage >= 95
        gates['finance_ar_coverage_pct'] = ar_coverage
        
        # finance_ar_clean: ALL AR invoices valid
        gates['finance_ar_clean'] = self._query_zero("""
            SELECT COUNT(*) AS c FROM invoices 
            WHERE status IN ('sent', 'overdue') AND paid_date IS NULL
            AND (client_id IS NULL OR due_date IS NULL)
        """)
        
        return gates
    
    def _check_data_integrity(self) -> bool:
        """Check ALL link status invariants from §3.4."""
        
        # Invariant 1: linked requires project exists AND work-ready
        inv1 = self._query_zero("""
            SELECT COUNT(*) AS c FROM tasks t
            LEFT JOIN projects p ON t.project_id = p.id
            LEFT JOIN brands b ON p.brand_id = b.id
            LEFT JOIN clients c ON b.client_id = c.id
            WHERE t.project_link_status = 'linked'
            AND (
                t.project_id IS NULL OR p.id IS NULL OR
                (COALESCE(p.is_internal, 0) = 0 AND (
                    p.brand_id IS NULL OR b.id IS NULL OR b.client_id IS NULL OR c.id IS NULL
                ))
            )
        """)
        
        # Invariant 2: unlinked has NULL project_id
        inv2 = self._query_zero("""
            SELECT COUNT(*) AS c FROM tasks WHERE project_link_status = 'unlinked' AND project_id IS NOT NULL
        """)
        
        # Invariant 3: partial has NOT NULL project_id
        inv3 = self._query_zero("""
            SELECT COUNT(*) AS c FROM tasks WHERE project_link_status = 'partial' AND project_id IS NULL
        """)
        
        # Invariant 4: partial must actually be broken (not resolvable)
        inv4 = self._query_zero("""
            SELECT COUNT(*) AS c FROM tasks t
            JOIN projects p ON t.project_id = p.id
            JOIN brands b ON p.brand_id = b.id
            JOIN clients c ON b.client_id = c.id
            WHERE t.project_link_status = 'partial'
            AND p.is_internal = 0
            AND p.brand_id IS NOT NULL
            AND b.client_id IS NOT NULL
            AND c.id IS NOT NULL
        """)
        
        # Invariant 5: client_link_status='linked' requires complete chain
        inv5 = self._query_zero("""
            SELECT COUNT(*) AS c FROM tasks t
            LEFT JOIN projects p ON t.project_id = p.id
            LEFT JOIN brands b ON t.brand_id = b.id
            LEFT JOIN clients c ON t.client_id = c.id
            WHERE t.client_link_status = 'linked'
            AND (
                t.client_id IS NULL OR c.id IS NULL OR
                t.brand_id IS NULL OR b.id IS NULL OR
                COALESCE(p.is_internal, 0) = 1
            )
        """)
        
        # Invariant 6: client_link_status='n/a' requires internal project
        inv6 = self._query_zero("""
            SELECT COUNT(*) AS c FROM tasks t
            LEFT JOIN projects p ON t.project_id = p.id
            WHERE t.client_link_status = 'n/a'
            AND (p.id IS NULL OR COALESCE(p.is_internal, 0) = 0)
        """)
        
        return all([inv1, inv2, inv3, inv4, inv5, inv6])
    
    def get_invariant_details(self) -> Dict[str, Dict]:
        """Get detailed results for each invariant."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        results = {}
        
        # Invariant 1
        cursor.execute("""
            SELECT COUNT(*) AS c FROM tasks t
            LEFT JOIN projects p ON t.project_id = p.id
            LEFT JOIN brands b ON p.brand_id = b.id
            LEFT JOIN clients c ON b.client_id = c.id
            WHERE t.project_link_status = 'linked'
            AND (
                t.project_id IS NULL OR p.id IS NULL OR
                (COALESCE(p.is_internal, 0) = 0 AND (
                    p.brand_id IS NULL OR b.id IS NULL OR b.client_id IS NULL OR c.id IS NULL
                ))
            )
        """)
        results['inv1_linked_valid'] = {'count': cursor.fetchone()['c'], 'pass': None}
        results['inv1_linked_valid']['pass'] = results['inv1_linked_valid']['count'] == 0
        
        # Invariant 2
        cursor.execute("""
            SELECT COUNT(*) AS c FROM tasks WHERE project_link_status = 'unlinked' AND project_id IS NOT NULL
        """)
        results['inv2_unlinked_null_project'] = {'count': cursor.fetchone()['c'], 'pass': None}
        results['inv2_unlinked_null_project']['pass'] = results['inv2_unlinked_null_project']['count'] == 0
        
        # Invariant 3
        cursor.execute("""
            SELECT COUNT(*) AS c FROM tasks WHERE project_link_status = 'partial' AND project_id IS NULL
        """)
        results['inv3_partial_has_project'] = {'count': cursor.fetchone()['c'], 'pass': None}
        results['inv3_partial_has_project']['pass'] = results['inv3_partial_has_project']['count'] == 0
        
        # Invariant 4
        cursor.execute("""
            SELECT COUNT(*) AS c FROM tasks t
            JOIN projects p ON t.project_id = p.id
            JOIN brands b ON p.brand_id = b.id
            JOIN clients c ON b.client_id = c.id
            WHERE t.project_link_status = 'partial'
            AND p.is_internal = 0
            AND p.brand_id IS NOT NULL
            AND b.client_id IS NOT NULL
            AND c.id IS NOT NULL
        """)
        results['inv4_partial_broken'] = {'count': cursor.fetchone()['c'], 'pass': None}
        results['inv4_partial_broken']['pass'] = results['inv4_partial_broken']['count'] == 0
        
        # Invariant 5
        cursor.execute("""
            SELECT COUNT(*) AS c FROM tasks t
            LEFT JOIN projects p ON t.project_id = p.id
            LEFT JOIN brands b ON t.brand_id = b.id
            LEFT JOIN clients c ON t.client_id = c.id
            WHERE t.client_link_status = 'linked'
            AND (
                t.client_id IS NULL OR c.id IS NULL OR
                t.brand_id IS NULL OR b.id IS NULL OR
                COALESCE(p.is_internal, 0) = 1
            )
        """)
        results['inv5_client_linked_valid'] = {'count': cursor.fetchone()['c'], 'pass': None}
        results['inv5_client_linked_valid']['pass'] = results['inv5_client_linked_valid']['count'] == 0
        
        # Invariant 6
        cursor.execute("""
            SELECT COUNT(*) AS c FROM tasks t
            LEFT JOIN projects p ON t.project_id = p.id
            WHERE t.client_link_status = 'n/a'
            AND (p.id IS NULL OR COALESCE(p.is_internal, 0) = 0)
        """)
        results['inv6_na_internal'] = {'count': cursor.fetchone()['c'], 'pass': None}
        results['inv6_na_internal']['pass'] = results['inv6_na_internal']['count'] == 0
        
        conn.close()
        return results


def evaluate_gates() -> Dict[str, Any]:
    """Convenience function to evaluate all gates."""
    evaluator = GateEvaluator()
    return evaluator.evaluate_all()


def check_data_integrity() -> bool:
    """Convenience function to check data integrity."""
    evaluator = GateEvaluator()
    return evaluator._check_data_integrity()


if __name__ == "__main__":
    print("Evaluating gates...")
    gates = evaluate_gates()
    
    print("\nGate Results:")
    for gate, result in gates.items():
        if gate.endswith('_pct'):
            continue
        status = "✓ PASS" if result else "✗ FAIL"
        if f"{gate}_pct" in gates:
            print(f"  {gate}: {status} ({gates[f'{gate}_pct']:.1f}%)")
        else:
            print(f"  {gate}: {status}")
    
    print("\nData Integrity Details:")
    evaluator = GateEvaluator()
    details = evaluator.get_invariant_details()
    for inv, data in details.items():
        status = "✓" if data['pass'] else "✗"
        print(f"  {inv}: {status} (count={data['count']})")
