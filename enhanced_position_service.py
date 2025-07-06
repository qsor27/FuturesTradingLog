"""
Enhanced Position Service with Overlap Prevention
Extends the original position service with comprehensive validation and overlap prevention
"""

from position_service import PositionService
from position_overlap_prevention import PositionOverlapPrevention
from typing import Dict, List, Any, Optional, Tuple
import logging

logger = logging.getLogger('enhanced_position_service')


class EnhancedPositionService(PositionService):
    """Enhanced position service with built-in overlap prevention and validation"""
    
    def __init__(self, db_path: str = None, enable_validation: bool = True):
        super().__init__(db_path)
        self.enable_validation = enable_validation
        self.validation_results = {}
        
    def rebuild_positions_from_trades_with_validation(self) -> Dict[str, Any]:
        """Rebuild positions with comprehensive validation and overlap prevention"""
        try:
            logger.info("Starting enhanced position rebuild with validation")
            
            # Clear existing positions
            self.cursor.execute("DELETE FROM positions")
            self.cursor.execute("DELETE FROM position_executions")
            
            # Get all non-deleted trades ordered by account, instrument, and execution ID
            self.cursor.execute("""
                SELECT * FROM trades 
                WHERE deleted = 0 OR deleted IS NULL
                ORDER BY account, instrument, id
            """)
            
            trades = [dict(row) for row in self.cursor.fetchall()]
            
            if not trades:
                return {
                    'success': True,
                    'positions_created': 0,
                    'trades_processed': 0,
                    'validation_results': {'message': 'No trades to process'}
                }
            
            # Group trades by account and instrument for position tracking
            account_instrument_groups = {}
            for trade in trades:
                account = (trade.get('account') or '').strip()
                instrument = (trade.get('instrument') or '').strip()
                
                if not account or not instrument:
                    logger.warning(f"Skipping trade with missing account/instrument: {trade.get('entry_execution_id', 'Unknown')}")
                    continue
                
                key = (account, instrument)
                if key not in account_instrument_groups:
                    account_instrument_groups[key] = []
                account_instrument_groups[key].append(trade)
            
            positions_created = 0
            trades_processed = 0
            validation_summary = {
                'groups_processed': 0,
                'groups_with_issues': 0,
                'total_warnings': 0,
                'total_errors': 0,
                'overlap_prevention_applied': 0
            }
            
            # Process each account-instrument combination with validation
            for (account, instrument), group_trades in account_instrument_groups.items():
                logger.info(f"Processing {len(group_trades)} trades for {account}/{instrument} with validation")
                
                # Enhanced position building with validation
                group_result = self._build_positions_with_validation(group_trades, account, instrument)
                
                # Save positions to database
                for position in group_result['positions']:
                    position_id = self._save_position(position)
                    if position_id:
                        positions_created += 1
                        trades_processed += len(position['executions'])
                
                # Update validation summary
                validation_summary['groups_processed'] += 1
                if group_result['validation_issues']:
                    validation_summary['groups_with_issues'] += 1
                validation_summary['total_warnings'] += len(group_result['warnings'])
                validation_summary['total_errors'] += len(group_result['errors'])
                if group_result['overlap_prevention_applied']:
                    validation_summary['overlap_prevention_applied'] += 1
                
                # Store detailed validation results
                self.validation_results[f"{account}/{instrument}"] = group_result
            
            self.conn.commit()
            
            result = {
                'success': True,
                'positions_created': positions_created,
                'trades_processed': trades_processed,
                'validation_summary': validation_summary,
                'validation_results': self.validation_results
            }
            
            logger.info(f"Enhanced rebuild complete: {positions_created} positions created from {trades_processed} trades")
            logger.info(f"Validation: {validation_summary['groups_with_issues']}/{validation_summary['groups_processed']} groups had issues")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in enhanced position rebuild: {e}")
            self.conn.rollback()
            return {
                'success': False,
                'error': str(e),
                'positions_created': 0,
                'trades_processed': 0
            }
    
    def _build_positions_with_validation(self, trades: List[Dict], account: str, instrument: str) -> Dict[str, Any]:
        """Build positions with comprehensive validation and overlap prevention"""
        result = {
            'positions': [],
            'warnings': [],
            'errors': [],
            'validation_issues': False,
            'overlap_prevention_applied': False
        }
        
        if not self.enable_validation:
            # Fall back to original algorithm
            positions = self._build_positions_from_execution_flow(trades, account, instrument)
            result['positions'] = positions
            return result
        
        # Step 1: Pre-validation of executions
        with PositionOverlapPrevention(self.db_path) as validator:
            pre_validation = validator.validate_executions_before_position_building(trades)
            
            if not pre_validation['valid']:
                result['errors'].extend(pre_validation['errors'])
                result['validation_issues'] = True
                logger.error(f"Pre-validation failed for {account}/{instrument}: {len(pre_validation['errors'])} errors")
                # Don't proceed with position building if there are critical errors
                return result
            
            if pre_validation['warnings']:
                result['warnings'].extend(pre_validation['warnings'])
                result['validation_issues'] = True
                logger.warning(f"Pre-validation warnings for {account}/{instrument}: {len(pre_validation['warnings'])} warnings")
            
            # Use corrected executions if available
            validated_trades = pre_validation.get('corrected_executions', trades)
        
        # Step 2: Build positions using validated executions
        try:
            positions = self._build_positions_from_execution_flow_validated(validated_trades, account, instrument)
            result['positions'] = positions
        except Exception as e:
            result['errors'].append({
                'type': 'position_building_error',
                'message': f"Error building positions: {str(e)}"
            })
            result['validation_issues'] = True
            return result
        
        # Step 3: Post-validation of built positions
        if positions:
            with PositionOverlapPrevention(self.db_path) as validator:
                post_validation = validator.validate_positions_after_building(positions, account, instrument)
                
                if not post_validation['valid']:
                    result['validation_issues'] = True
                    logger.warning(f"Post-validation detected issues for {account}/{instrument}")
                    
                    # Apply overlap fixes if possible
                    fixes = validator.suggest_overlap_fixes(post_validation)
                    if fixes:
                        result['overlap_prevention_applied'] = True
                        logger.info(f"Applying {len(fixes)} overlap fixes for {account}/{instrument}")
                        
                        # Apply fixes and rebuild positions
                        try:
                            fixed_positions = self._apply_overlap_fixes(positions, fixes, validated_trades, account, instrument)
                            result['positions'] = fixed_positions
                            logger.info(f"Successfully applied overlap fixes for {account}/{instrument}")
                        except Exception as e:
                            result['errors'].append({
                                'type': 'overlap_fix_error',
                                'message': f"Error applying overlap fixes: {str(e)}"
                            })
                            # Keep original positions if fixes fail
                    
                    # Add validation issues to warnings
                    for overlap in post_validation.get('overlaps', []):
                        result['warnings'].append({
                            'type': 'position_overlap',
                            'message': overlap['message'],
                            'severity': overlap['severity']
                        })
                    
                    for violation in post_validation.get('boundary_violations', []):
                        result['warnings'].append({
                            'type': 'boundary_violation',
                            'message': violation['message'],
                            'severity': violation['severity']
                        })
        
        return result
    
    def _build_positions_from_execution_flow_validated(self, executions: List[Dict], account: str, instrument: str) -> List[Dict]:
        """Enhanced position building with additional validation checks"""
        if not executions:
            return []
        
        positions = []
        current_position = None
        running_quantity = 0
        
        logger.info(f"=== VALIDATED POSITION BUILDING FOR {account}/{instrument} ===")
        logger.info(f"Processing {len(executions)} validated executions")
        
        for i, execution in enumerate(executions):
            quantity = abs(int(execution.get('quantity', 0)))
            action = execution.get('side_of_market', '').strip()
            
            # Convert to signed quantity change
            if action in ["Buy", "Long"]:
                signed_qty_change = quantity
            elif action in ["Sell", "Short"]: 
                signed_qty_change = -quantity
            else:
                logger.error(f"Invalid action '{action}' in validated execution {execution.get('entry_execution_id', 'Unknown')}")
                continue
            
            previous_quantity = running_quantity
            running_quantity += signed_qty_change
            
            logger.info(f"Execution {i+1}: {action} {quantity} contracts | Running: {previous_quantity} → {running_quantity}")
            
            # Enhanced position lifecycle logic with validation
            if previous_quantity == 0 and running_quantity != 0:
                # Starting new position (0 → non-zero)
                current_position = {
                    'instrument': instrument,
                    'account': account,
                    'position_type': 'Long' if running_quantity > 0 else 'Short',
                    'entry_time': execution.get('entry_time'),
                    'executions': [execution],
                    'total_quantity': abs(running_quantity),
                    'max_quantity': abs(running_quantity),
                    'position_status': 'open',
                    'execution_count': 1,
                    'validation_metadata': {
                        'creation_method': 'validated_flow',
                        'start_execution_id': execution.get('entry_execution_id'),
                        'start_quantity': running_quantity
                    }
                }
                logger.info(f"  → Started new validated {current_position['position_type']} position")
                
            elif current_position and running_quantity == 0:
                # Closing position (non-zero → 0)
                current_position['executions'].append(execution)
                current_position['position_status'] = 'closed'
                current_position['execution_count'] = len(current_position['executions'])
                current_position['validation_metadata']['end_execution_id'] = execution.get('entry_execution_id')
                current_position['validation_metadata']['end_quantity'] = running_quantity
                
                # Determine correct position type
                self._determine_position_type_from_executions(current_position)
                
                # Calculate position totals
                self._calculate_position_totals_from_executions(current_position)
                
                # Validate position before adding
                if self._validate_individual_position(current_position):
                    positions.append(current_position)
                    logger.info(f"  → Closed validated position with {current_position['execution_count']} executions")
                else:
                    logger.warning(f"  → Rejected invalid position with {current_position['execution_count']} executions")
                
                current_position = None
                
            elif current_position and running_quantity != 0:
                # Modifying existing position (non-zero → non-zero)
                
                # Additional validation: check for direction changes
                if ((current_position['validation_metadata']['start_quantity'] > 0 and running_quantity < 0) or
                    (current_position['validation_metadata']['start_quantity'] < 0 and running_quantity > 0)):
                    logger.error(f"  → VALIDATION ERROR: Direction change without zero crossing detected!")
                    logger.error(f"      Start quantity: {current_position['validation_metadata']['start_quantity']}")
                    logger.error(f"      Current quantity: {running_quantity}")
                    # This should have been caught in pre-validation, but add extra safety
                    continue
                
                current_position['executions'].append(execution)
                current_position['total_quantity'] = abs(running_quantity)
                current_position['max_quantity'] = max(current_position['max_quantity'], abs(running_quantity))
                current_position['execution_count'] = len(current_position['executions'])
                
                if abs(running_quantity) > abs(previous_quantity):
                    logger.info(f"  → Added to validated {current_position['position_type']} position, new quantity: {abs(running_quantity)}")
                else:
                    logger.info(f"  → Reduced validated {current_position['position_type']} position, new quantity: {abs(running_quantity)}")
        
        # Handle any remaining open position
        if current_position:
            current_position['position_status'] = 'open'
            current_position['validation_metadata']['is_open'] = True
            self._calculate_position_totals_from_executions(current_position)
            
            if self._validate_individual_position(current_position):
                positions.append(current_position)
                logger.info(f"  → Saved validated open position with {current_position['execution_count']} executions")
            else:
                logger.warning(f"  → Rejected invalid open position with {current_position['execution_count']} executions")
        
        logger.info(f"Validated position building complete: {len(positions)} positions created")
        return positions
    
    def _validate_individual_position(self, position: Dict) -> bool:
        """Validate an individual position for basic consistency"""
        try:
            # Check required fields
            required_fields = ['instrument', 'account', 'position_type', 'entry_time', 'executions']
            for field in required_fields:
                if field not in position or position[field] is None:
                    logger.error(f"Position missing required field: {field}")
                    return False
            
            # Check executions exist
            if not position['executions'] or len(position['executions']) == 0:
                logger.error("Position has no executions")
                return False
            
            # Check position type is valid
            if position['position_type'] not in ['Long', 'Short']:
                logger.error(f"Invalid position type: {position['position_type']}")
                return False
            
            # Check quantities are positive
            if position.get('total_quantity', 0) <= 0:
                logger.error(f"Invalid total quantity: {position.get('total_quantity')}")
                return False
            
            # Additional validation can be added here
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating position: {e}")
            return False
    
    def _apply_overlap_fixes(self, positions: List[Dict], fixes: List[Dict], 
                           original_executions: List[Dict], account: str, instrument: str) -> List[Dict]:
        """Apply overlap fixes to positions"""
        logger.info(f"Applying {len(fixes)} overlap fixes for {account}/{instrument}")
        
        # For now, implement the most common fix: merge overlapping positions
        fixed_positions = positions.copy()
        
        for fix in fixes:
            if fix['fix_type'] == 'merge_positions':
                affected_ids = fix['affected_positions']
                logger.info(f"Merging positions: {affected_ids}")
                
                # Find positions to merge
                positions_to_merge = [p for p in fixed_positions if p.get('id') in affected_ids]
                
                if len(positions_to_merge) >= 2:
                    # Create merged position
                    merged_position = self._merge_positions(positions_to_merge)
                    
                    # Remove original positions
                    fixed_positions = [p for p in fixed_positions if p.get('id') not in affected_ids]
                    
                    # Add merged position
                    fixed_positions.append(merged_position)
                    
                    logger.info(f"Successfully merged {len(positions_to_merge)} positions")
            
            elif fix['fix_type'] == 'rebuild_positions':
                # For serious issues, rebuild positions from scratch with stricter validation
                logger.info("Rebuilding positions with stricter validation due to boundary violations")
                
                # Use original position building algorithm but with extra validation
                try:
                    rebuilt_positions = self._build_positions_from_execution_flow(original_executions, account, instrument)
                    fixed_positions = rebuilt_positions
                    logger.info(f"Successfully rebuilt {len(rebuilt_positions)} positions")
                except Exception as e:
                    logger.error(f"Error rebuilding positions: {e}")
                    # Keep original positions if rebuild fails
        
        return fixed_positions
    
    def _merge_positions(self, positions: List[Dict]) -> Dict:
        """Merge multiple positions into a single position"""
        if not positions:
            raise ValueError("No positions to merge")
        
        if len(positions) == 1:
            return positions[0]
        
        # Sort positions by entry time
        sorted_positions = sorted(positions, key=lambda p: p.get('entry_time', ''))
        
        # Create merged position based on first position
        merged = sorted_positions[0].copy()
        
        # Merge executions from all positions
        all_executions = []
        for pos in sorted_positions:
            all_executions.extend(pos.get('executions', []))
        
        # Sort executions by time
        all_executions = sorted(all_executions, key=lambda e: e.get('entry_time', ''))
        
        # Update merged position
        merged['executions'] = all_executions
        merged['execution_count'] = len(all_executions)
        merged['entry_time'] = all_executions[0].get('entry_time')
        
        # Set exit time from last execution if position is closed
        if all(p.get('position_status') == 'closed' for p in sorted_positions):
            merged['exit_time'] = all_executions[-1].get('entry_time')
            merged['position_status'] = 'closed'
        else:
            merged['position_status'] = 'open'
            merged['exit_time'] = None
        
        # Recalculate totals
        self._calculate_position_totals_from_executions(merged)
        
        # Add merge metadata
        merged['validation_metadata'] = {
            'merged_from_positions': len(positions),
            'merge_reason': 'overlap_prevention',
            'original_position_ids': [p.get('id') for p in positions]
        }
        
        return merged
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of validation results from last rebuild"""
        if not self.validation_results:
            return {'message': 'No validation results available. Run rebuild_positions_from_trades_with_validation() first.'}
        
        summary = {
            'total_groups': len(self.validation_results),
            'groups_with_issues': 0,
            'total_warnings': 0,
            'total_errors': 0,
            'overlap_prevention_applied': 0,
            'group_details': {}
        }
        
        for group_key, group_result in self.validation_results.items():
            group_summary = {
                'positions_created': len(group_result['positions']),
                'warnings': len(group_result['warnings']),
                'errors': len(group_result['errors']),
                'validation_issues': group_result['validation_issues'],
                'overlap_prevention_applied': group_result['overlap_prevention_applied']
            }
            
            summary['group_details'][group_key] = group_summary
            
            if group_result['validation_issues']:
                summary['groups_with_issues'] += 1
            
            summary['total_warnings'] += len(group_result['warnings'])
            summary['total_errors'] += len(group_result['errors'])
            
            if group_result['overlap_prevention_applied']:
                summary['overlap_prevention_applied'] += 1
        
        return summary