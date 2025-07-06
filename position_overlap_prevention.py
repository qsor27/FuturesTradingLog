"""
Position Overlap Prevention System
Comprehensive validation and prevention mechanisms for position overlaps
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import logging

logger = logging.getLogger('position_overlap_prevention')


class PositionOverlapPrevention:
    """Comprehensive position overlap prevention and validation system"""
    
    def __init__(self, db_path: str = None):
        from config import config
        self.db_path = db_path or config.db_path
        
    def __enter__(self):
        """Establish database connection when entering context"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close database connection when exiting context"""
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()
    
    def validate_executions_before_position_building(self, executions: List[Dict]) -> Dict[str, Any]:
        """Comprehensive validation of executions before position building"""
        validation_results = {
            'valid': True,
            'warnings': [],
            'errors': [],
            'corrected_executions': []
        }
        
        # 1. Timestamp validation
        timestamp_issues = self._validate_timestamps(executions)
        validation_results['warnings'].extend(timestamp_issues['warnings'])
        validation_results['errors'].extend(timestamp_issues['errors'])
        
        # 2. Data integrity validation
        integrity_issues = self._validate_data_integrity(executions)
        validation_results['warnings'].extend(integrity_issues['warnings'])
        validation_results['errors'].extend(integrity_issues['errors'])
        
        # 3. Quantity flow validation
        flow_issues = self._validate_quantity_flow_preview(executions)
        validation_results['warnings'].extend(flow_issues['warnings'])
        validation_results['errors'].extend(flow_issues['errors'])
        
        # 4. Duplicate detection
        duplicate_issues = self._detect_execution_duplicates(executions)
        validation_results['warnings'].extend(duplicate_issues['warnings'])
        validation_results['errors'].extend(duplicate_issues['errors'])
        
        # Determine overall validity
        validation_results['valid'] = len(validation_results['errors']) == 0
        
        # Apply corrections if possible
        if validation_results['valid'] or len(validation_results['errors']) == 0:
            validation_results['corrected_executions'] = self._apply_execution_corrections(executions, validation_results)
        
        return validation_results
    
    def _validate_timestamps(self, executions: List[Dict]) -> Dict[str, List]:
        """Validate timestamp integrity and consistency"""
        issues = {'warnings': [], 'errors': []}
        
        for i, execution in enumerate(executions):
            exec_id = execution.get('entry_execution_id', f'execution_{i}')
            timestamp = execution.get('entry_time')
            
            # Check timestamp exists
            if not timestamp:
                issues['errors'].append({
                    'type': 'missing_timestamp',
                    'execution_id': exec_id,
                    'message': 'Execution missing entry_time'
                })
                continue
            
            # Check timestamp format
            try:
                if isinstance(timestamp, str):
                    # Try multiple timestamp formats
                    parsed_time = None
                    formats = [
                        '%Y-%m-%d %H:%M:%S',
                        '%Y-%m-%d %H:%M:%S.%f',
                        '%Y-%m-%dT%H:%M:%S',
                        '%Y-%m-%dT%H:%M:%S.%f',
                        '%Y-%m-%dT%H:%M:%SZ',
                        '%m/%d/%Y %I:%M:%S %p'  # NinjaTrader format
                    ]
                    
                    for fmt in formats:
                        try:
                            parsed_time = datetime.strptime(timestamp, fmt)
                            break
                        except ValueError:
                            continue
                    
                    if not parsed_time:
                        issues['errors'].append({
                            'type': 'invalid_timestamp_format',
                            'execution_id': exec_id,
                            'timestamp': timestamp,
                            'message': f'Cannot parse timestamp: {timestamp}'
                        })
                        continue
                    
                    # Store parsed time for further validation
                    execution['_parsed_time'] = parsed_time
                    
            except Exception as e:
                issues['errors'].append({
                    'type': 'timestamp_parsing_error',
                    'execution_id': exec_id,
                    'timestamp': timestamp,
                    'message': f'Error parsing timestamp: {str(e)}'
                })
        
        # Check chronological order
        sorted_executions = sorted(
            [ex for ex in executions if '_parsed_time' in ex], 
            key=lambda x: x['_parsed_time']
        )
        
        for i in range(len(sorted_executions) - 1):
            current = sorted_executions[i]
            next_exec = sorted_executions[i + 1]
            
            # Check for simultaneous executions
            if current['_parsed_time'] == next_exec['_parsed_time']:
                issues['warnings'].append({
                    'type': 'simultaneous_executions',
                    'execution_ids': [
                        current.get('entry_execution_id', 'unknown'),
                        next_exec.get('entry_execution_id', 'unknown')
                    ],
                    'timestamp': current['entry_time'],
                    'message': 'Executions have identical timestamps'
                })
        
        return issues
    
    def _validate_data_integrity(self, executions: List[Dict]) -> Dict[str, List]:
        """Validate execution data integrity"""
        issues = {'warnings': [], 'errors': []}
        
        for i, execution in enumerate(executions):
            exec_id = execution.get('entry_execution_id', f'execution_{i}')
            
            # Check required fields
            required_fields = ['side_of_market', 'quantity', 'entry_price', 'instrument', 'account']
            for field in required_fields:
                if field not in execution or execution[field] is None:
                    issues['errors'].append({
                        'type': 'missing_required_field',
                        'execution_id': exec_id,
                        'field': field,
                        'message': f'Missing required field: {field}'
                    })
            
            # Validate side_of_market
            side = execution.get('side_of_market', '').strip()
            if side not in ['Buy', 'Sell', 'Long', 'Short']:
                issues['errors'].append({
                    'type': 'invalid_side_of_market',
                    'execution_id': exec_id,
                    'side': side,
                    'message': f'Invalid side_of_market: {side}'
                })
            
            # Validate quantity
            try:
                quantity = float(execution.get('quantity', 0))
                if quantity <= 0:
                    issues['errors'].append({
                        'type': 'invalid_quantity',
                        'execution_id': exec_id,
                        'quantity': quantity,
                        'message': f'Quantity must be positive: {quantity}'
                    })
                elif quantity != int(quantity):
                    issues['warnings'].append({
                        'type': 'fractional_quantity',
                        'execution_id': exec_id,
                        'quantity': quantity,
                        'message': f'Fractional quantity detected: {quantity}'
                    })
            except (ValueError, TypeError):
                issues['errors'].append({
                    'type': 'invalid_quantity_format',
                    'execution_id': exec_id,
                    'quantity': execution.get('quantity'),
                    'message': f'Cannot parse quantity: {execution.get("quantity")}'
                })
            
            # Validate price
            try:
                price = float(execution.get('entry_price', 0))
                if price <= 0:
                    issues['errors'].append({
                        'type': 'invalid_price',
                        'execution_id': exec_id,
                        'price': price,
                        'message': f'Price must be positive: {price}'
                    })
            except (ValueError, TypeError):
                issues['errors'].append({
                    'type': 'invalid_price_format',
                    'execution_id': exec_id,
                    'price': execution.get('entry_price'),
                    'message': f'Cannot parse price: {execution.get("entry_price")}'
                })
        
        return issues
    
    def _validate_quantity_flow_preview(self, executions: List[Dict]) -> Dict[str, List]:
        """Preview quantity flow validation without building positions"""
        issues = {'warnings': [], 'errors': []}
        
        if not executions:
            return issues
        
        # Sort executions by time
        try:
            sorted_executions = sorted(executions, key=lambda x: x.get('entry_time', ''))
        except:
            # If sorting fails, work with original order
            sorted_executions = executions
        
        running_quantity = 0
        position_count = 0
        
        for i, execution in enumerate(sorted_executions):
            exec_id = execution.get('entry_execution_id', f'execution_{i}')
            
            try:
                quantity = abs(int(execution.get('quantity', 0)))
                action = execution.get('side_of_market', '').strip()
                
                # Calculate signed quantity change
                if action in ['Buy', 'Long']:
                    signed_qty_change = quantity
                elif action in ['Sell', 'Short']:
                    signed_qty_change = -quantity
                else:
                    continue  # Skip invalid actions (already caught in data integrity)
                
                previous_quantity = running_quantity
                running_quantity += signed_qty_change
                
                # Check for invalid direction changes
                if (previous_quantity != 0 and running_quantity != 0 and
                    ((previous_quantity > 0 and running_quantity < 0) or
                     (previous_quantity < 0 and running_quantity > 0))):
                    issues['errors'].append({
                        'type': 'direction_change_without_zero',
                        'execution_id': exec_id,
                        'previous_quantity': previous_quantity,
                        'new_quantity': running_quantity,
                        'message': f'Position changed direction without reaching zero: {previous_quantity} → {running_quantity}'
                    })
                
                # Track position boundaries
                if previous_quantity == 0 and running_quantity != 0:
                    position_count += 1
                elif previous_quantity != 0 and running_quantity == 0:
                    # Position ended normally
                    pass
                
            except (ValueError, TypeError) as e:
                # Data errors already caught in integrity validation
                continue
        
        # Check final quantity
        if running_quantity != 0:
            issues['warnings'].append({
                'type': 'unclosed_position',
                'final_quantity': running_quantity,
                'message': f'Final quantity is {running_quantity}, expected 0 (position remains open)'
            })
        
        # Log flow summary
        logger.info(f"Quantity flow preview: {len(sorted_executions)} executions → {position_count} positions, final quantity: {running_quantity}")
        
        return issues
    
    def _detect_execution_duplicates(self, executions: List[Dict]) -> Dict[str, List]:
        """Detect duplicate executions"""
        issues = {'warnings': [], 'errors': []}
        
        # Check for duplicate execution IDs
        seen_ids = set()
        for execution in executions:
            exec_id = execution.get('entry_execution_id')
            if exec_id:
                if exec_id in seen_ids:
                    issues['warnings'].append({
                        'type': 'duplicate_execution_id',
                        'execution_id': exec_id,
                        'message': f'Duplicate execution ID: {exec_id}'
                    })
                else:
                    seen_ids.add(exec_id)
        
        # Check for potential semantic duplicates (same time, price, quantity, side)
        for i in range(len(executions)):
            for j in range(i + 1, len(executions)):
                exec1 = executions[i]
                exec2 = executions[j]
                
                # Compare key fields
                if (exec1.get('entry_time') == exec2.get('entry_time') and
                    exec1.get('entry_price') == exec2.get('entry_price') and
                    exec1.get('quantity') == exec2.get('quantity') and
                    exec1.get('side_of_market') == exec2.get('side_of_market')):
                    
                    issues['warnings'].append({
                        'type': 'potential_semantic_duplicate',
                        'execution_ids': [
                            exec1.get('entry_execution_id', f'execution_{i}'),
                            exec2.get('entry_execution_id', f'execution_{j}')
                        ],
                        'message': 'Executions have identical time, price, quantity, and side'
                    })
        
        return issues
    
    def _apply_execution_corrections(self, executions: List[Dict], validation_results: Dict) -> List[Dict]:
        """Apply automatic corrections to executions where possible"""
        corrected = executions.copy()
        
        # Apply timestamp corrections
        for execution in corrected:
            if '_parsed_time' in execution:
                # Ensure consistent timestamp format
                execution['entry_time'] = execution['_parsed_time'].strftime('%Y-%m-%d %H:%M:%S')
                del execution['_parsed_time']
        
        # Sort by corrected timestamps
        try:
            corrected = sorted(corrected, key=lambda x: x.get('entry_time', ''))
        except:
            pass
        
        return corrected
    
    def validate_positions_after_building(self, positions: List[Dict], account: str, instrument: str) -> Dict[str, Any]:
        """Validate positions after they've been built to detect overlaps"""
        validation_results = {
            'valid': True,
            'overlaps': [],
            'boundary_violations': [],
            'consistency_issues': []
        }
        
        if len(positions) < 2:
            return validation_results
        
        # Sort positions by entry time
        sorted_positions = sorted(positions, key=lambda p: p.get('entry_time', ''))
        
        for i in range(len(sorted_positions) - 1):
            current = sorted_positions[i]
            next_pos = sorted_positions[i + 1]
            
            # Check for time overlaps
            time_overlap = self._check_position_time_overlap(current, next_pos)
            if time_overlap:
                validation_results['overlaps'].append(time_overlap)
                validation_results['valid'] = False
            
            # Check for boundary violations
            boundary_violation = self._check_position_boundary(current, next_pos)
            if boundary_violation:
                validation_results['boundary_violations'].append(boundary_violation)
                validation_results['valid'] = False
            
            # Check for consistency issues
            consistency_issue = self._check_position_consistency(current, next_pos)
            if consistency_issue:
                validation_results['consistency_issues'].append(consistency_issue)
        
        return validation_results
    
    def _check_position_time_overlap(self, pos1: Dict, pos2: Dict) -> Optional[Dict]:
        """Check if two positions overlap in time"""
        # If first position is still open
        if pos1.get('position_status') == 'open':
            return {
                'type': 'open_position_overlap',
                'position1_id': pos1.get('id'),
                'position2_id': pos2.get('id'),
                'message': f"Position {pos1.get('id')} is still open when position {pos2.get('id')} starts",
                'severity': 'high'
            }
        
        # Check time overlap for closed positions
        if pos1.get('exit_time') and pos2.get('entry_time'):
            try:
                exit_time = datetime.fromisoformat(pos1['exit_time'].replace('Z', '+00:00'))
                entry_time = datetime.fromisoformat(pos2['entry_time'].replace('Z', '+00:00'))
                
                if exit_time > entry_time:
                    overlap_duration = exit_time - entry_time
                    return {
                        'type': 'time_overlap',
                        'position1_id': pos1.get('id'),
                        'position2_id': pos2.get('id'),
                        'overlap_duration_seconds': overlap_duration.total_seconds(),
                        'message': f"Position {pos1.get('id')} ends after position {pos2.get('id')} starts",
                        'severity': 'high'
                    }
            except ValueError:
                return {
                    'type': 'timestamp_parse_error',
                    'position1_id': pos1.get('id'),
                    'position2_id': pos2.get('id'),
                    'message': 'Cannot parse position timestamps for overlap detection',
                    'severity': 'medium'
                }
        
        return None
    
    def _check_position_boundary(self, pos1: Dict, pos2: Dict) -> Optional[Dict]:
        """Check for position boundary violations"""
        # Check if both positions are the same type (both Long or both Short)
        if pos1.get('position_type') == pos2.get('position_type'):
            return {
                'type': 'same_direction_boundary_violation',
                'position1_id': pos1.get('id'),
                'position2_id': pos2.get('id'),
                'position_type': pos1.get('position_type'),
                'message': f"Both positions are {pos1.get('position_type')} - missing zero crossing",
                'severity': 'high'
            }
        
        return None
    
    def _check_position_consistency(self, pos1: Dict, pos2: Dict) -> Optional[Dict]:
        """Check for position consistency issues"""
        issues = []
        
        # Check if both positions have only one execution
        if (pos1.get('execution_count', 0) == 1 and 
            pos2.get('execution_count', 0) == 1):
            issues.append('both_single_execution')
        
        # Check for suspicious P&L patterns
        if (pos1.get('total_dollars_pnl', 0) == 0 and 
            pos2.get('total_dollars_pnl', 0) == 0):
            issues.append('both_zero_pnl')
        
        # Check for identical quantities
        if (pos1.get('total_quantity') == pos2.get('total_quantity') and
            pos1.get('average_entry_price') == pos2.get('average_entry_price')):
            issues.append('identical_position_details')
        
        if issues:
            return {
                'type': 'consistency_issues',
                'position1_id': pos1.get('id'),
                'position2_id': pos2.get('id'),
                'issues': issues,
                'message': f"Consistency issues detected: {', '.join(issues)}",
                'severity': 'medium'
            }
        
        return None
    
    def suggest_overlap_fixes(self, validation_results: Dict) -> List[Dict]:
        """Suggest fixes for detected overlaps and violations"""
        fixes = []
        
        # Fixes for overlaps
        for overlap in validation_results.get('overlaps', []):
            if overlap['type'] == 'time_overlap':
                fixes.append({
                    'fix_type': 'merge_positions',
                    'affected_positions': [overlap['position1_id'], overlap['position2_id']],
                    'action': 'Merge overlapping positions into a single position',
                    'reasoning': 'Time overlap indicates these should be one continuous position',
                    'priority': 'high'
                })
            elif overlap['type'] == 'open_position_overlap':
                fixes.append({
                    'fix_type': 'extend_first_position',
                    'affected_positions': [overlap['position1_id'], overlap['position2_id']],
                    'action': 'Extend first position to include second position executions',
                    'reasoning': 'First position was never properly closed',
                    'priority': 'high'
                })
        
        # Fixes for boundary violations
        for violation in validation_results.get('boundary_violations', []):
            if violation['type'] == 'same_direction_boundary_violation':
                fixes.append({
                    'fix_type': 'rebuild_positions',
                    'affected_positions': [violation['position1_id'], violation['position2_id']],
                    'action': 'Rebuild positions from raw executions with corrected quantity flow',
                    'reasoning': 'Positions should not have same direction without zero crossing',
                    'priority': 'high'
                })
        
        # Fixes for consistency issues
        for issue in validation_results.get('consistency_issues', []):
            if 'both_single_execution' in issue.get('issues', []):
                fixes.append({
                    'fix_type': 'investigate_split',
                    'affected_positions': [issue['position1_id'], issue['position2_id']],
                    'action': 'Investigate if these single-execution positions should be merged',
                    'reasoning': 'Adjacent single-execution positions may indicate incorrect splitting',
                    'priority': 'medium'
                })
        
        return fixes
    
    def generate_prevention_report(self, account: str = None, instrument: str = None) -> str:
        """Generate comprehensive overlap prevention report"""
        report = []
        report.append("=" * 80)
        report.append("POSITION OVERLAP PREVENTION REPORT")
        report.append("=" * 80)
        report.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if account and instrument:
            report.append(f"Scope: {account}/{instrument}")
        elif account:
            report.append(f"Scope: Account {account}")
        else:
            report.append("Scope: All accounts and instruments")
        
        report.append("")
        
        # Get positions to analyze
        if account and instrument:
            where_clause = "WHERE account = ? AND instrument = ?"
            params = [account, instrument]
        elif account:
            where_clause = "WHERE account = ?"
            params = [account]
        else:
            where_clause = ""
            params = []
        
        self.cursor.execute(f"""
            SELECT * FROM positions 
            {where_clause}
            ORDER BY account, instrument, entry_time
        """, params)
        
        positions = [dict(row) for row in self.cursor.fetchall()]
        
        if not positions:
            report.append("No positions found to analyze.")
            return "\n".join(report)
        
        # Group positions by account/instrument
        grouped = {}
        for pos in positions:
            key = (pos['account'], pos['instrument'])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(pos)
        
        total_overlaps = 0
        total_violations = 0
        
        report.append(f"ANALYSIS SUMMARY")
        report.append("-" * 40)
        report.append(f"Total positions: {len(positions)}")
        report.append(f"Account/instrument groups: {len(grouped)}")
        report.append("")
        
        # Analyze each group
        for (acc, instr), group in grouped.items():
            report.append(f"GROUP: {acc}/{instr}")
            report.append("-" * 40)
            report.append(f"Positions: {len(group)}")
            
            if len(group) < 2:
                report.append("No overlaps possible (single position)")
                report.append("")
                continue
            
            # Validate this group
            validation = self.validate_positions_after_building(group, acc, instr)
            
            group_overlaps = len(validation['overlaps'])
            group_violations = len(validation['boundary_violations'])
            group_issues = len(validation['consistency_issues'])
            
            total_overlaps += group_overlaps
            total_violations += group_violations
            
            report.append(f"Overlaps: {group_overlaps}")
            report.append(f"Boundary violations: {group_violations}")
            report.append(f"Consistency issues: {group_issues}")
            report.append(f"Overall valid: {validation['valid']}")
            
            # Detail violations
            if validation['overlaps']:
                report.append("OVERLAPS:")
                for overlap in validation['overlaps']:
                    report.append(f"  - {overlap['type']}: Positions {overlap['position1_id']} & {overlap['position2_id']}")
                    report.append(f"    {overlap['message']}")
            
            if validation['boundary_violations']:
                report.append("BOUNDARY VIOLATIONS:")
                for violation in validation['boundary_violations']:
                    report.append(f"  - {violation['type']}: Positions {violation['position1_id']} & {violation['position2_id']}")
                    report.append(f"    {violation['message']}")
            
            # Suggest fixes
            if not validation['valid']:
                fixes = self.suggest_overlap_fixes(validation)
                if fixes:
                    report.append("SUGGESTED FIXES:")
                    for fix in fixes:
                        report.append(f"  - {fix['fix_type']}: {fix['action']}")
                        report.append(f"    Reasoning: {fix['reasoning']}")
                        report.append(f"    Priority: {fix['priority']}")
            
            report.append("")
        
        # Overall summary
        report.append("OVERALL SUMMARY")
        report.append("-" * 40)
        report.append(f"Total overlaps detected: {total_overlaps}")
        report.append(f"Total boundary violations: {total_violations}")
        
        if total_overlaps > 0 or total_violations > 0:
            report.append("")
            report.append("RECOMMENDATIONS:")
            report.append("1. Run position rebuild with validation enabled")
            report.append("2. Review execution import process for data quality")
            report.append("3. Implement pre-import validation")
            report.append("4. Consider automated overlap detection in position building")
        
        report.append("=" * 80)
        return "\n".join(report)