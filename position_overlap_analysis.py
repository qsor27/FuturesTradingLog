"""
Position Overlap Analysis Tool
Analyzes the position building algorithm for potential overlap issues
"""

import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from position_service import PositionService
from TradingLog_db import FuturesDB


class PositionOverlapAnalyzer:
    """Analyzer for detecting and preventing position overlaps"""
    
    def __init__(self, db_path: str = None):
        from config import config
        self.db_path = db_path or config.db_path
        
    def analyze_current_positions(self) -> Dict[str, Any]:
        """Analyze current positions for potential overlaps"""
        with FuturesDB() as db:
            # Get all positions ordered by account, instrument, and time
            db.cursor.execute("""
                SELECT id, instrument, account, position_type, entry_time, exit_time, 
                       position_status, total_quantity, execution_count
                FROM positions 
                ORDER BY account, instrument, entry_time
            """)
            positions = [dict(row) for row in db.cursor.fetchall()]
        
        if not positions:
            return {"message": "No positions to analyze", "overlaps": []}
            
        # Group positions by account and instrument
        grouped = {}
        for pos in positions:
            key = (pos['account'], pos['instrument'])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(pos)
        
        overlaps = []
        for (account, instrument), group in grouped.items():
            group_overlaps = self._detect_overlaps_in_group(group, account, instrument)
            overlaps.extend(group_overlaps)
        
        return {
            "total_positions": len(positions),
            "groups_analyzed": len(grouped),
            "overlaps_found": len(overlaps),
            "overlaps": overlaps
        }
    
    def _detect_overlaps_in_group(self, positions: List[Dict], account: str, instrument: str) -> List[Dict]:
        """Detect overlaps within a group of positions for the same account/instrument"""
        overlaps = []
        
        if len(positions) < 2:
            return overlaps
            
        # Sort positions by entry time
        positions_sorted = sorted(positions, key=lambda p: p['entry_time'])
        
        for i in range(len(positions_sorted) - 1):
            current = positions_sorted[i]
            next_pos = positions_sorted[i + 1]
            
            # Check for time-based overlaps
            overlap_info = self._check_time_overlap(current, next_pos)
            if overlap_info:
                overlaps.append({
                    'type': 'time_overlap',
                    'account': account,
                    'instrument': instrument,
                    'position1': current,
                    'position2': next_pos,
                    'overlap_info': overlap_info
                })
            
            # Check for quantity consistency issues
            consistency_issues = self._check_quantity_consistency(current, next_pos)
            if consistency_issues:
                overlaps.append({
                    'type': 'quantity_inconsistency',
                    'account': account,
                    'instrument': instrument,
                    'position1': current,
                    'position2': next_pos,
                    'issues': consistency_issues
                })
        
        return overlaps
    
    def _check_time_overlap(self, pos1: Dict, pos2: Dict) -> Optional[Dict]:
        """Check if two positions have overlapping time periods"""
        # If pos1 is still open, it extends indefinitely
        if pos1['position_status'] == 'open':
            return {
                'reason': 'open_position_before_closed',
                'details': f"Position {pos1['id']} is still open when position {pos2['id']} starts"
            }
        
        # If pos1 is closed, check if it ends after pos2 starts
        if pos1['exit_time'] and pos2['entry_time']:
            try:
                exit_time = datetime.fromisoformat(pos1['exit_time'].replace('Z', '+00:00'))
                entry_time = datetime.fromisoformat(pos2['entry_time'].replace('Z', '+00:00'))
                
                if exit_time > entry_time:
                    return {
                        'reason': 'time_overlap',
                        'details': f"Position {pos1['id']} ends at {pos1['exit_time']} after position {pos2['id']} starts at {pos2['entry_time']}"
                    }
            except ValueError:
                return {
                    'reason': 'invalid_timestamps',
                    'details': f"Cannot parse timestamps: {pos1['exit_time']} vs {pos2['entry_time']}"
                }
        
        return None
    
    def _check_quantity_consistency(self, pos1: Dict, pos2: Dict) -> List[Dict]:
        """Check for quantity consistency issues between adjacent positions"""
        issues = []
        
        # Check if both positions are the same type (both Long or both Short)
        if pos1['position_type'] == pos2['position_type']:
            issues.append({
                'issue': 'same_position_type',
                'details': f"Both positions are {pos1['position_type']} - possible missing zero crossing"
            })
        
        # Check execution count consistency
        if pos1['execution_count'] == 1 and pos2['execution_count'] == 1:
            issues.append({
                'issue': 'both_single_execution',
                'details': "Both positions have only 1 execution - possible incorrect position splitting"
            })
        
        return issues
    
    def validate_position_boundaries(self) -> Dict[str, Any]:
        """Validate that positions follow proper 0 → +/- → 0 boundaries"""
        with FuturesDB() as db:
            # Get all trades ordered by account, instrument, and time
            db.cursor.execute("""
                SELECT id, instrument, account, side_of_market, quantity, entry_time, 
                       entry_execution_id, deleted
                FROM trades 
                WHERE deleted = 0 OR deleted IS NULL
                ORDER BY account, instrument, entry_time
            """)
            trades = [dict(row) for row in db.cursor.fetchall()]
        
        if not trades:
            return {"message": "No trades to validate", "boundary_violations": []}
        
        # Group trades by account and instrument
        grouped = {}
        for trade in trades:
            key = (trade['account'], trade['instrument'])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(trade)
        
        violations = []
        for (account, instrument), group in grouped.items():
            group_violations = self._validate_quantity_flow(group, account, instrument)
            violations.extend(group_violations)
        
        return {
            "total_trades": len(trades),
            "groups_analyzed": len(grouped),
            "boundary_violations": len(violations),
            "violations": violations
        }
    
    def _validate_quantity_flow(self, trades: List[Dict], account: str, instrument: str) -> List[Dict]:
        """Validate the quantity flow for a group of trades"""
        violations = []
        running_quantity = 0
        position_starts = []
        
        for i, trade in enumerate(trades):
            try:
                quantity = abs(int(trade['quantity']))
                action = trade['side_of_market'].strip()
                
                # Calculate signed quantity change
                if action == "Buy":
                    signed_qty_change = quantity
                elif action == "Sell":
                    signed_qty_change = -quantity
                else:
                    violations.append({
                        'type': 'unknown_action',
                        'account': account,
                        'instrument': instrument,
                        'trade_id': trade['id'],
                        'action': action,
                        'details': f"Unknown side_of_market: {action}"
                    })
                    continue
                
                previous_quantity = running_quantity
                running_quantity += signed_qty_change
                
                # Check for position boundary violations
                if previous_quantity == 0 and running_quantity != 0:
                    # Starting new position
                    position_starts.append({
                        'trade_id': trade['id'],
                        'start_quantity': running_quantity,
                        'start_time': trade['entry_time']
                    })
                
                elif previous_quantity != 0 and running_quantity == 0:
                    # Ending position - this is expected
                    if position_starts:
                        position_starts.pop()  # Remove the completed position
                
                elif previous_quantity != 0 and running_quantity != 0:
                    # Continuing position - check for direction change without zero crossing
                    if (previous_quantity > 0 and running_quantity < 0) or (previous_quantity < 0 and running_quantity > 0):
                        violations.append({
                            'type': 'direction_change_without_zero',
                            'account': account,
                            'instrument': instrument,
                            'trade_id': trade['id'],
                            'previous_quantity': previous_quantity,
                            'new_quantity': running_quantity,
                            'details': f"Position changed from {previous_quantity} to {running_quantity} without crossing zero"
                        })
                
            except (ValueError, TypeError) as e:
                violations.append({
                    'type': 'data_error',
                    'account': account,
                    'instrument': instrument,
                    'trade_id': trade['id'],
                    'details': f"Error processing trade data: {str(e)}"
                })
        
        # Check for unclosed positions
        if running_quantity != 0:
            violations.append({
                'type': 'unclosed_position',
                'account': account,
                'instrument': instrument,
                'final_quantity': running_quantity,
                'details': f"Final quantity is {running_quantity}, expected 0"
            })
        
        return violations
    
    def suggest_overlap_fixes(self, overlaps: List[Dict]) -> List[Dict]:
        """Suggest fixes for detected overlaps"""
        fixes = []
        
        for overlap in overlaps:
            if overlap['type'] == 'time_overlap':
                fixes.append({
                    'overlap_id': f"{overlap['position1']['id']}_{overlap['position2']['id']}",
                    'fix_type': 'merge_positions',
                    'action': 'Merge overlapping positions into a single position',
                    'details': f"Combine executions from positions {overlap['position1']['id']} and {overlap['position2']['id']}"
                })
            
            elif overlap['type'] == 'quantity_inconsistency':
                fixes.append({
                    'overlap_id': f"{overlap['position1']['id']}_{overlap['position2']['id']}",
                    'fix_type': 'rebuild_positions',
                    'action': 'Rebuild positions from raw executions',
                    'details': f"Re-process executions for {overlap['account']}/{overlap['instrument']} to fix quantity flow"
                })
        
        return fixes
    
    def generate_overlap_report(self) -> str:
        """Generate a comprehensive overlap analysis report"""
        overlap_analysis = self.analyze_current_positions()
        boundary_validation = self.validate_position_boundaries()
        
        report = []
        report.append("=" * 80)
        report.append("POSITION OVERLAP ANALYSIS REPORT")
        report.append("=" * 80)
        report.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Position overlap analysis
        report.append("1. POSITION OVERLAP ANALYSIS")
        report.append("-" * 40)
        report.append(f"Total positions analyzed: {overlap_analysis['total_positions']}")
        report.append(f"Account/instrument groups: {overlap_analysis['groups_analyzed']}")
        report.append(f"Overlaps found: {overlap_analysis['overlaps_found']}")
        report.append("")
        
        if overlap_analysis['overlaps']:
            report.append("DETECTED OVERLAPS:")
            for i, overlap in enumerate(overlap_analysis['overlaps']):
                report.append(f"  {i+1}. {overlap['type'].upper()}")
                report.append(f"     Account: {overlap['account']}")
                report.append(f"     Instrument: {overlap['instrument']}")
                report.append(f"     Position 1: ID {overlap['position1']['id']} ({overlap['position1']['entry_time']} - {overlap['position1']['exit_time']})")
                report.append(f"     Position 2: ID {overlap['position2']['id']} ({overlap['position2']['entry_time']} - {overlap['position2']['exit_time']})")
                if 'overlap_info' in overlap:
                    report.append(f"     Issue: {overlap['overlap_info']['reason']}")
                    report.append(f"     Details: {overlap['overlap_info']['details']}")
                report.append("")
        
        # Boundary validation
        report.append("2. POSITION BOUNDARY VALIDATION")
        report.append("-" * 40)
        report.append(f"Total trades analyzed: {boundary_validation['total_trades']}")
        report.append(f"Account/instrument groups: {boundary_validation['groups_analyzed']}")
        report.append(f"Boundary violations: {boundary_validation['boundary_violations']}")
        report.append("")
        
        if boundary_validation['violations']:
            report.append("BOUNDARY VIOLATIONS:")
            for i, violation in enumerate(boundary_validation['violations']):
                report.append(f"  {i+1}. {violation['type'].upper()}")
                report.append(f"     Account: {violation['account']}")
                report.append(f"     Instrument: {violation['instrument']}")
                report.append(f"     Trade ID: {violation['trade_id']}")
                report.append(f"     Details: {violation['details']}")
                report.append("")
        
        # Suggestions
        if overlap_analysis['overlaps']:
            fixes = self.suggest_overlap_fixes(overlap_analysis['overlaps'])
            report.append("3. SUGGESTED FIXES")
            report.append("-" * 40)
            for fix in fixes:
                report.append(f"Fix for {fix['overlap_id']}: {fix['action']}")
                report.append(f"  Details: {fix['details']}")
                report.append("")
        
        report.append("=" * 80)
        return "\n".join(report)


def main():
    """Run the position overlap analysis"""
    analyzer = PositionOverlapAnalyzer()
    
    print("Analyzing position overlaps...")
    report = analyzer.generate_overlap_report()
    print(report)
    
    # Save report to file
    report_path = "/home/qadmin/Projects/FuturesTradingLog/position_overlap_report.txt"
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()