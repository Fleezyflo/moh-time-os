"""
Single DB Write Module - All writes go through here.

After every write:
1. Normalizer runs
2. Gates evaluate
3. Resolution queue refreshes
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional
import json

DB_PATH = Path(__file__).parent.parent / "data" / "state.db"


class DBWriter:
    """Single point for all database writes. Triggers pipeline after each write."""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._last_gate_results = {}
    
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    
    def _run_pipeline(self) -> Dict[str, Any]:
        """Run post-write pipeline: Normalize → Gates → Resolution Queue."""
        from lib.normalizer import Normalizer
        from lib.gates import GateEvaluator
        from lib.resolution_queue import populate_queue
        
        results = {}
        
        # 1. Normalizer
        normalizer = Normalizer(self.db_path)
        results['normalizer'] = normalizer.run()
        
        # 2. Gates
        evaluator = GateEvaluator(self.db_path)
        results['gates'] = evaluator.evaluate_all()
        self._last_gate_results = results['gates']
        
        # 3. Resolution Queue
        results['resolution_queue'] = populate_queue()
        
        return results
    
    def insert(self, table: str, data: Dict) -> tuple[str, Dict]:
        """Insert row, run pipeline. Returns (id, pipeline_results)."""
        conn = self._get_conn()
        try:
            columns = list(data.keys())
            placeholders = ["?" for _ in columns]
            values = [json.dumps(v) if isinstance(v, (dict, list)) else v for v in data.values()]
            
            cursor = conn.cursor()
            cursor.execute(
                f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join(placeholders)})",
                values
            )
            conn.commit()
            row_id = data.get('id', cursor.lastrowid)
        finally:
            conn.close()
        
        pipeline = self._run_pipeline()
        return row_id, pipeline
    
    def update(self, table: str, row_id: str, data: Dict) -> Dict:
        """Update row, run pipeline. Returns pipeline_results."""
        conn = self._get_conn()
        try:
            sets = [f"{k} = ?" for k in data.keys()]
            values = [json.dumps(v) if isinstance(v, (dict, list)) else v for v in data.values()]
            values.append(row_id)
            
            conn.execute(
                f"UPDATE {table} SET {', '.join(sets)} WHERE id = ?",
                values
            )
            conn.commit()
        finally:
            conn.close()
        
        return self._run_pipeline()
    
    def delete(self, table: str, row_id: str) -> Dict:
        """Delete row, run pipeline. Returns pipeline_results."""
        conn = self._get_conn()
        try:
            conn.execute(f"DELETE FROM {table} WHERE id = ?", [row_id])
            conn.commit()
        finally:
            conn.close()
        
        return self._run_pipeline()
    
    def execute(self, sql: str, params: List = None) -> Dict:
        """Execute arbitrary write SQL, run pipeline."""
        conn = self._get_conn()
        try:
            conn.execute(sql, params or [])
            conn.commit()
        finally:
            conn.close()
        
        return self._run_pipeline()
    
    def get_last_gates(self) -> Dict:
        """Get most recent gate evaluation results."""
        return self._last_gate_results


# Singleton
_writer = None

def get_writer() -> DBWriter:
    global _writer
    if _writer is None:
        _writer = DBWriter()
    return _writer
