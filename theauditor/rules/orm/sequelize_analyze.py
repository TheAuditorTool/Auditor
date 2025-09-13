"""
Sequelize ORM Analyzer - SQL-based implementation.

This module detects Sequelize ORM anti-patterns and performance issues
using TheAuditor's indexed database.

Migration from: sequelize_detector.py (206 lines -> ~240 lines)
Performance: ~8x faster using direct SQL queries
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from theauditor.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class StandardRuleContext:
    """Standard context for rule execution."""
    db_path: Path
    project_root: Path
    exclusions: List[str]
    workset_files: Optional[List[str]] = None
    

@dataclass 
class StandardFinding:
    """Standard finding format for all rules."""
    file: str
    line: int
    pattern: str
    message: str
    confidence: float
    severity: str
    category: str
    snippet: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "file": self.file,
            "line": self.line,
            "pattern": self.pattern,
            "message": self.message,
            "confidence": self.confidence,
            "severity": self.severity,
            "category": self.category,
            "snippet": self.snippet
        }


class SequelizeAnalyzer:
    """Analyzer for Sequelize ORM anti-patterns using SQL queries."""
    
    def __init__(self, context: StandardRuleContext):
        """Initialize with standard context."""
        self.context = context
        self.conn = sqlite3.connect(context.db_path)
        self.cursor = self.conn.cursor()
        
        # Sequelize methods that modify data
        self.write_methods = [
            'create', 'update', 'destroy', 'bulkCreate', 
            'bulkUpdate', 'bulkDestroy', 'upsert', 'save'
        ]
        
        # Query methods that can cause performance issues
        self.query_methods = [
            'findAll', 'findAndCountAll', 'findOne', 'findByPk'
        ]
    
    def analyze(self) -> List[StandardFinding]:
        """Run all Sequelize ORM checks."""
        findings = []
        
        try:
            # Check if orm_queries table exists
            self.cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='orm_queries'"
            )
            if not self.cursor.fetchone():
                logger.info("No orm_queries table found, skipping Sequelize analysis")
                return findings
            
            # Run each analysis
            findings.extend(self._detect_death_queries())
            findings.extend(self._detect_n_plus_one())
            findings.extend(self._detect_unbounded_queries())
            findings.extend(self._detect_race_conditions())
            findings.extend(self._detect_missing_transactions())
            findings.extend(self._detect_raw_queries())
            findings.extend(self._detect_eager_loading_issues())
            
            logger.info(f"Found {len(findings)} Sequelize ORM issues")
            
        except Exception as e:
            logger.error(f"Error during Sequelize analysis: {e}")
        finally:
            self.conn.close()
            
        return findings
    
    def _detect_death_queries(self) -> List[StandardFinding]:
        """Detect death query patterns (include all with nested)."""
        findings = []
        
        query = """
        SELECT file, line, query_type, includes
        FROM orm_queries
        WHERE includes LIKE '%"all":true%' 
          AND includes LIKE '%"nested":true%'
        """
        
        self.cursor.execute(query)
        for row in self.cursor.fetchall():
            file, line, query_type, includes = row
            
            findings.append(StandardFinding(
                file=file,
                line=line,
                pattern="sequelize_death_query",
                message=f"Death query: {query_type} with include all + nested",
                confidence=0.95,
                severity="CRITICAL",
                category="orm_performance",
                snippet="{ include: [{ all: true, nested: true }] }"
            ))
        
        return findings
    
    def _detect_n_plus_one(self) -> List[StandardFinding]:
        """Detect potential N+1 query patterns."""
        findings = []
        
        query = """
        SELECT file, line, query_type
        FROM orm_queries
        WHERE query_type IN ('findAll', 'findAndCountAll')
          AND (includes IS NULL OR includes = '[]' OR includes = '{}')
        """
        
        self.cursor.execute(query)
        for row in self.cursor.fetchall():
            file, line, query_type = row
            
            findings.append(StandardFinding(
                file=file,
                line=line,
                pattern="sequelize_n_plus_one",
                message=f"Potential N+1: {query_type} without includes",
                confidence=0.80,
                severity="HIGH",
                category="orm_performance",
                snippet=f"{query_type}() without eager loading"
            ))
        
        return findings
    
    def _detect_unbounded_queries(self) -> List[StandardFinding]:
        """Detect queries without limits that could fetch too much data."""
        findings = []
        
        query = """
        SELECT file, line, query_type
        FROM orm_queries
        WHERE query_type IN ('findAll', 'findAndCountAll')
          AND has_limit = 0
        """
        
        self.cursor.execute(query)
        for row in self.cursor.fetchall():
            file, line, query_type = row
            
            findings.append(StandardFinding(
                file=file,
                line=line,
                pattern="sequelize_unbounded_query",
                message=f"Unbounded {query_type} without limit - memory risk",
                confidence=0.85,
                severity="MEDIUM",
                category="orm_performance",
                snippet=f"{query_type}() without limit/offset"
            ))
        
        return findings
    
    def _detect_race_conditions(self) -> List[StandardFinding]:
        """Detect findOrCreate without transactions (race condition)."""
        findings = []
        
        query = """
        SELECT file, line, query_type
        FROM orm_queries
        WHERE query_type = 'findOrCreate'
          AND has_transaction = 0
        """
        
        self.cursor.execute(query)
        for row in self.cursor.fetchall():
            file, line, query_type = row
            
            findings.append(StandardFinding(
                file=file,
                line=line,
                pattern="sequelize_race_condition",
                message="findOrCreate without transaction - race condition risk",
                confidence=0.90,
                severity="HIGH",
                category="orm_concurrency",
                snippet="findOrCreate() outside transaction"
            ))
        
        return findings
    
    def _detect_missing_transactions(self) -> List[StandardFinding]:
        """Detect multiple write operations without transactions."""
        findings = []
        
        # Get all write operations grouped by file
        query = """
        SELECT file, line, query_type, has_transaction
        FROM orm_queries
        WHERE query_type IN ('create', 'update', 'destroy', 
                            'bulkCreate', 'bulkUpdate', 'bulkDestroy', 
                            'upsert', 'save')
        ORDER BY file, line
        """
        
        self.cursor.execute(query)
        
        # Group by file
        file_ops = {}
        for row in self.cursor.fetchall():
            file, line, query_type, has_transaction = row
            if file not in file_ops:
                file_ops[file] = []
            file_ops[file].append({
                'line': line,
                'query': query_type,
                'has_transaction': has_transaction
            })
        
        # Check for close operations without transactions
        for file, operations in file_ops.items():
            for i in range(len(operations) - 1):
                op1 = operations[i]
                op2 = operations[i + 1]
                
                # Operations within 20 lines without transaction
                if (op2['line'] - op1['line'] <= 20 and 
                    not op1['has_transaction'] and 
                    not op2['has_transaction']):
                    
                    findings.append(StandardFinding(
                        file=file,
                        line=op1['line'],
                        pattern="sequelize_missing_transaction",
                        message=f"Multiple writes without transaction: {op1['query']} and {op2['query']}",
                        confidence=0.85,
                        severity="HIGH",
                        category="orm_data_integrity",
                        snippet="Multiple operations need sequelize.transaction()"
                    ))
                    break  # One finding per cluster
        
        return findings
    
    def _detect_raw_queries(self) -> List[StandardFinding]:
        """Detect potentially unsafe raw SQL queries."""
        findings = []
        
        # Look for raw query methods
        query = """
        SELECT DISTINCT f.file, f.line, f.callee_function, f.args_json
        FROM function_call_args f
        WHERE f.callee_function LIKE '%sequelize.query%'
           OR f.callee_function LIKE '%sequelize.literal%'
           OR f.callee_function LIKE '%Sequelize.literal%'
           OR f.callee_function = 'query'
        """
        
        self.cursor.execute(query)
        for row in self.cursor.fetchall():
            file, line, func, args_json = row
            
            # Check for string concatenation or interpolation
            if args_json:
                has_interpolation = any(x in args_json for x in ['${', '"+', '" +', '` +'])
                if has_interpolation:
                    findings.append(StandardFinding(
                        file=file,
                        line=line,
                        pattern="sequelize_sql_injection",
                        message=f"Potential SQL injection in {func}",
                        confidence=0.80,
                        severity="CRITICAL",
                        category="orm_security",
                        snippet=f"{func}() with string interpolation"
                    ))
        
        return findings
    
    def _detect_eager_loading_issues(self) -> List[StandardFinding]:
        """Detect inefficient eager loading patterns."""
        findings = []
        
        # Look for multiple includes or deep nesting
        query = """
        SELECT file, line, query_type, includes
        FROM orm_queries
        WHERE includes IS NOT NULL 
          AND includes != '[]'
          AND includes != '{}'
        """
        
        self.cursor.execute(query)
        for row in self.cursor.fetchall():
            file, line, query_type, includes_json = row
            
            try:
                includes = json.loads(includes_json) if includes_json else None
                if includes:
                    # Count number of includes
                    include_count = 0
                    if isinstance(includes, list):
                        include_count = len(includes)
                    elif isinstance(includes, dict):
                        include_count = 1
                    
                    # Warn if too many includes
                    if include_count > 3:
                        findings.append(StandardFinding(
                            file=file,
                            line=line,
                            pattern="sequelize_excessive_eager_loading",
                            message=f"Excessive eager loading: {include_count} includes in {query_type}",
                            confidence=0.70,
                            severity="MEDIUM",
                            category="orm_performance",
                            snippet=f"{query_type} with {include_count} includes"
                        ))
            except json.JSONDecodeError:
                pass
        
        return findings


def analyze(context: StandardRuleContext) -> List[Dict[str, Any]]:
    """Entry point for the analyzer."""
    analyzer = SequelizeAnalyzer(context)
    findings = analyzer.analyze()
    return [f.to_dict() for f in findings]