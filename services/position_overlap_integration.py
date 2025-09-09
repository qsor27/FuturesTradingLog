"""
Position Overlap Prevention Integration
Integrates validation with the enhanced position building algorithm
"""

import logging
from typing import Dict, List, Any
from services.enhanced_position_service_v2 import EnhancedPositionServiceV2 as PositionService
from services.position_overlap_prevention import PositionOverlapPrevention

logger = logging.getLogger(__name__)


class EnhancedPositionBuilder:
    """Enhanced position builder with integrated overlap prevention"""
    
    def __init__(self, db_path: str = None):
        self.position_service = PositionService(db_path)
        self.validator = PositionOverlapPrevention(db_path)
    
    def build_positions_with_validation(self, raw_executions: List[Dict], account: str, instrument: str) -> Dict[str, Any]:
        """
        Build positions from executions with comprehensive validation and overlap prevention.
        
        Returns:
            Dict containing:
            - success: bool
            - positions: List of validated positions
            - validation_results: Validation details
            - warnings: Any warnings encountered
            - errors: Any errors that occurred
        """
        result = {
            'success': False,
            'positions': [],
            'validation_results': {},
            'warnings': [],
            'errors': []
        }
        
        try:
            logger.info(f"Building positions for {account}/{instrument} with {len(raw_executions)} executions")
            
            # Step 1: Validate executions before position building
            with self.validator as validator:
                validation_results = validator.validate_executions_before_position_building(raw_executions)
                result['validation_results'] = validation_results
                
                if not validation_results['valid']:
                    result['errors'].extend(validation_results['errors'])
                    logger.error(f"Execution data failed validation: {validation_results['errors']}")
                    return result
                
                # Use corrected executions if validator provides them
                executions_to_process = validation_results.get('corrected_executions', raw_executions)
                result['warnings'].extend(validation_results['warnings'])
            
            # Step 2: Build positions using the enhanced algorithm with overlap prevention
            with self.position_service as pos_service:
                positions = pos_service._aggregate_executions_into_positions(
                    executions=executions_to_process,
                    account=account,
                    instrument=instrument
                )
                
                result['positions'] = positions
                result['success'] = True
                
                logger.info(f"Successfully built {len(positions)} positions with overlap prevention")
                
                # Step 3: Post-build validation to ensure no overlaps occurred
                overlap_check = self._validate_position_boundaries(positions)
                if overlap_check['overlaps_found']:
                    result['warnings'].append(f"Post-build validation found potential issues: {overlap_check['issues']}")
                else:
                    logger.info("Post-build validation: No position overlaps detected")
                
        except Exception as e:
            logger.error(f"Error building positions with validation: {e}")
            result['errors'].append(str(e))
            
        return result
    
    def _validate_position_boundaries(self, positions: List[Dict]) -> Dict[str, Any]:
        """
        Validate that positions have clear boundaries with no overlaps.
        
        Returns validation results including any overlaps found.
        """
        validation = {
            'overlaps_found': False,
            'issues': [],
            'position_count': len(positions)
        }
        
        if len(positions) < 2:
            return validation  # Can't have overlaps with fewer than 2 positions
        
        # Sort positions by entry time for chronological analysis
        sorted_positions = sorted(positions, key=lambda p: p.get('entry_time', ''))
        
        for i in range(len(sorted_positions) - 1):
            current_pos = sorted_positions[i]
            next_pos = sorted_positions[i + 1]
            
            current_exit = current_pos.get('exit_time')
            next_entry = next_pos.get('entry_time')
            
            # Check for temporal overlap
            if current_exit and next_entry:
                if current_exit > next_entry:
                    validation['overlaps_found'] = True
                    validation['issues'].append({
                        'type': 'temporal_overlap',
                        'position_1': current_pos.get('id', i),
                        'position_2': next_pos.get('id', i + 1),
                        'current_exit': current_exit,
                        'next_entry': next_entry
                    })
            
            # Check for position type consistency (should alternate properly)
            if (current_pos['position_status'] == 'closed' and 
                current_pos['position_type'] == next_pos['position_type']):
                # Same position type following each other might indicate missed reversal
                validation['issues'].append({
                    'type': 'same_type_sequence',
                    'message': f"Consecutive {current_pos['position_type']} positions detected",
                    'position_1': current_pos.get('id', i),
                    'position_2': next_pos.get('id', i + 1)
                })
        
        return validation
    
    def rebuild_all_positions_with_validation(self) -> Dict[str, Any]:
        """
        Rebuild all positions from trades with comprehensive validation.
        """
        try:
            with self.position_service as pos_service:
                # Get all trades for validation
                pos_service.cursor.execute("""
                    SELECT * FROM trades 
                    WHERE deleted = 0 OR deleted IS NULL
                    ORDER BY account, instrument, entry_time, id
                """)
                all_trades = [dict(row) for row in pos_service.cursor.fetchall()]
                
                if not all_trades:
                    return {'success': True, 'message': 'No trades to process', 'positions_created': 0}
                
                # Group trades by account and instrument
                grouped_trades = {}
                for trade in all_trades:
                    account = (trade.get('account') or '').strip()
                    instrument = (trade.get('instrument') or '').strip()
                    
                    if not account or not instrument:
                        continue
                    
                    key = (account, instrument)
                    if key not in grouped_trades:
                        grouped_trades[key] = []
                    grouped_trades[key].append(trade)
                
                # Clear existing positions
                pos_service.cursor.execute("DELETE FROM positions")
                pos_service.cursor.execute("DELETE FROM position_executions")
                
                total_positions = 0
                total_warnings = []
                total_errors = []
                
                # Process each group with validation
                for (account, instrument), trades in grouped_trades.items():
                    result = self.build_positions_with_validation(trades, account, instrument)
                    
                    if result['success']:
                        # Save positions to database
                        for position in result['positions']:
                            position_id = pos_service._save_position(position)
                            if position_id:
                                total_positions += 1
                    
                    total_warnings.extend(result['warnings'])
                    total_errors.extend(result['errors'])
                
                pos_service.conn.commit()
                
                return {
                    'success': len(total_errors) == 0,
                    'positions_created': total_positions,
                    'groups_processed': len(grouped_trades),
                    'warnings': total_warnings,
                    'errors': total_errors
                }
                
        except Exception as e:
            logger.error(f"Error rebuilding positions with validation: {e}")
            return {'success': False, 'error': str(e)}


# Convenience function for easy integration
def rebuild_positions_with_overlap_prevention(db_path: str = None) -> Dict[str, Any]:
    """Convenience function to rebuild all positions with overlap prevention"""
    builder = EnhancedPositionBuilder(db_path)
    return builder.rebuild_all_positions_with_validation()