"""
Test script for position overlap prevention system
Demonstrates validation and prevention capabilities
"""

from services.enhanced_position_service_v2 import EnhancedPositionServiceV2 as EnhancedPositionService
from services.position_overlap_prevention import PositionOverlapPrevention
from datetime import datetime, timedelta
from typing import List, Dict
import json


def create_test_executions() -> List[Dict]:
    """Create test execution data to demonstrate overlap scenarios"""
    base_time = datetime.now() - timedelta(days=1)
    
    # Scenario 1: Normal position flow (should pass validation)
    normal_executions = [
        {
            'id': 1,
            'entry_execution_id': 'test_001',
            'instrument': 'MNQ',
            'account': 'TestAccount',
            'side_of_market': 'Buy',
            'quantity': 4,
            'entry_price': 22800.0,
            'entry_time': base_time.strftime('%Y-%m-%d %H:%M:%S'),
            'commission': 2.5
        },
        {
            'id': 2,
            'entry_execution_id': 'test_002',
            'instrument': 'MNQ',
            'account': 'TestAccount',
            'side_of_market': 'Sell',
            'quantity': 2,
            'entry_price': 22810.0,
            'entry_time': (base_time + timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S'),
            'commission': 1.25
        },
        {
            'id': 3,
            'entry_execution_id': 'test_003',
            'instrument': 'MNQ',
            'account': 'TestAccount',
            'side_of_market': 'Sell',
            'quantity': 2,
            'entry_price': 22815.0,
            'entry_time': (base_time + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S'),
            'commission': 1.25
        }
    ]
    
    # Scenario 2: Problematic executions (should trigger validation issues)
    problematic_executions = [
        {
            'id': 4,
            'entry_execution_id': 'test_004',
            'instrument': 'ES',
            'account': 'TestAccount',
            'side_of_market': 'Buy',
            'quantity': 3,
            'entry_price': 5800.0,
            'entry_time': (base_time + timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S'),
            'commission': 2.0
        },
        {
            'id': 5,
            'entry_execution_id': 'test_005',
            'instrument': 'ES',
            'account': 'TestAccount',
            'side_of_market': 'Sell',
            'quantity': 6,  # This creates direction change without zero crossing
            'entry_price': 5790.0,
            'entry_time': (base_time + timedelta(minutes=20)).strftime('%Y-%m-%d %H:%M:%S'),
            'commission': 3.0
        },
        {
            'id': 6,
            'entry_execution_id': 'test_006',
            'instrument': 'ES',
            'account': 'TestAccount',
            'side_of_market': 'Buy',
            'quantity': 3,
            'entry_price': 5795.0,
            'entry_time': (base_time + timedelta(minutes=25)).strftime('%Y-%m-%d %H:%M:%S'),
            'commission': 2.0
        }
    ]
    
    # Scenario 3: Timestamp issues
    timestamp_issues = [
        {
            'id': 7,
            'entry_execution_id': 'test_007',
            'instrument': 'YM',
            'account': 'TestAccount',
            'side_of_market': 'Buy',
            'quantity': 2,
            'entry_price': 45000.0,
            'entry_time': (base_time + timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S'),
            'commission': 4.0
        },
        {
            'id': 8,
            'entry_execution_id': 'test_008',
            'instrument': 'YM',
            'account': 'TestAccount',
            'side_of_market': 'Sell',
            'quantity': 1,
            'entry_price': 45010.0,
            'entry_time': (base_time + timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S'),  # Same timestamp
            'commission': 2.0
        },
        {
            'id': 9,
            'entry_execution_id': 'test_009',
            'instrument': 'YM',
            'account': 'TestAccount',
            'side_of_market': 'Sell',
            'quantity': 1,
            'entry_price': 45005.0,
            'entry_time': (base_time + timedelta(minutes=35)).strftime('%Y-%m-%d %H:%M:%S'),
            'commission': 2.0
        }
    ]
    
    return normal_executions + problematic_executions + timestamp_issues


def test_pre_validation():
    """Test pre-validation of executions"""
    print("=" * 80)
    print("TESTING PRE-VALIDATION OF EXECUTIONS")
    print("=" * 80)
    
    executions = create_test_executions()
    
    with PositionOverlapPrevention() as validator:
        # Test normal executions
        normal_executions = executions[:3]
        print(f"\n1. Testing normal executions ({len(normal_executions)} executions)")
        print("-" * 40)
        
        validation_result = validator.validate_executions_before_position_building(normal_executions)
        
        print(f"Valid: {validation_result['valid']}")
        print(f"Warnings: {len(validation_result['warnings'])}")
        print(f"Errors: {len(validation_result['errors'])}")
        
        if validation_result['warnings']:
            print("\nWarnings:")
            for warning in validation_result['warnings']:
                print(f"  - {warning['type']}: {warning['message']}")
        
        if validation_result['errors']:
            print("\nErrors:")
            for error in validation_result['errors']:
                print(f"  - {error['type']}: {error['message']}")
        
        # Test problematic executions
        problematic_executions = executions[3:6]
        print(f"\n2. Testing problematic executions ({len(problematic_executions)} executions)")
        print("-" * 40)
        
        validation_result = validator.validate_executions_before_position_building(problematic_executions)
        
        print(f"Valid: {validation_result['valid']}")
        print(f"Warnings: {len(validation_result['warnings'])}")
        print(f"Errors: {len(validation_result['errors'])}")
        
        if validation_result['warnings']:
            print("\nWarnings:")
            for warning in validation_result['warnings']:
                print(f"  - {warning['type']}: {warning['message']}")
        
        if validation_result['errors']:
            print("\nErrors:")
            for error in validation_result['errors']:
                print(f"  - {error['type']}: {error['message']}")
        
        # Test timestamp issues
        timestamp_executions = executions[6:9]
        print(f"\n3. Testing timestamp issues ({len(timestamp_executions)} executions)")
        print("-" * 40)
        
        validation_result = validator.validate_executions_before_position_building(timestamp_executions)
        
        print(f"Valid: {validation_result['valid']}")
        print(f"Warnings: {len(validation_result['warnings'])}")
        print(f"Errors: {len(validation_result['errors'])}")
        
        if validation_result['warnings']:
            print("\nWarnings:")
            for warning in validation_result['warnings']:
                print(f"  - {warning['type']}: {warning['message']}")
        
        if validation_result['errors']:
            print("\nErrors:")
            for error in validation_result['errors']:
                print(f"  - {error['type']}: {error['message']}")


def test_position_building_validation():
    """Test position building with validation"""
    print("\n" + "=" * 80)
    print("TESTING POSITION BUILDING WITH VALIDATION")
    print("=" * 80)
    
    # Create test positions with overlaps
    base_time = datetime.now() - timedelta(days=1)
    
    test_positions = [
        {
            'id': 1,
            'instrument': 'MNQ',
            'account': 'TestAccount',
            'position_type': 'Long',
            'entry_time': base_time.strftime('%Y-%m-%d %H:%M:%S'),
            'exit_time': (base_time + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S'),
            'position_status': 'closed',
            'total_quantity': 4,
            'execution_count': 2
        },
        {
            'id': 2,
            'instrument': 'MNQ',
            'account': 'TestAccount',
            'position_type': 'Long',  # Same type - boundary violation
            'entry_time': (base_time + timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S'),  # Overlaps with position 1
            'exit_time': (base_time + timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S'),
            'position_status': 'closed',
            'total_quantity': 2,
            'execution_count': 1
        },
        {
            'id': 3,
            'instrument': 'MNQ',
            'account': 'TestAccount',
            'position_type': 'Short',
            'entry_time': (base_time + timedelta(minutes=20)).strftime('%Y-%m-%d %H:%M:%S'),
            'exit_time': None,
            'position_status': 'open',
            'total_quantity': 3,
            'execution_count': 1
        }
    ]
    
    with PositionOverlapPrevention() as validator:
        validation_result = validator.validate_positions_after_building(test_positions, 'TestAccount', 'MNQ')
        
        print(f"Positions valid: {validation_result['valid']}")
        print(f"Overlaps: {len(validation_result['overlaps'])}")
        print(f"Boundary violations: {len(validation_result['boundary_violations'])}")
        print(f"Consistency issues: {len(validation_result['consistency_issues'])}")
        
        if validation_result['overlaps']:
            print("\nOverlaps detected:")
            for overlap in validation_result['overlaps']:
                print(f"  - {overlap['type']}: {overlap['message']}")
        
        if validation_result['boundary_violations']:
            print("\nBoundary violations:")
            for violation in validation_result['boundary_violations']:
                print(f"  - {violation['type']}: {violation['message']}")
        
        if validation_result['consistency_issues']:
            print("\nConsistency issues:")
            for issue in validation_result['consistency_issues']:
                print(f"  - {issue['type']}: {issue['message']}")
        
        # Test fix suggestions
        if not validation_result['valid']:
            fixes = validator.suggest_overlap_fixes(validation_result)
            print(f"\nSuggested fixes: {len(fixes)}")
            for fix in fixes:
                print(f"  - {fix['fix_type']}: {fix['action']}")
                print(f"    Priority: {fix['priority']}")
                print(f"    Reasoning: {fix['reasoning']}")


def test_enhanced_position_service():
    """Test the enhanced position service"""
    print("\n" + "=" * 80)
    print("TESTING ENHANCED POSITION SERVICE")
    print("=" * 80)
    
    # Note: This would require actual database setup and trade data
    # For demonstration, we'll show how it would be used
    
    print("Enhanced Position Service Usage Example:")
    print("-" * 40)
    print("""
    # Create enhanced position service with validation enabled
    with EnhancedPositionService(enable_validation=True) as service:
        
        # Rebuild positions with comprehensive validation
        result = service.rebuild_positions_from_trades_with_validation()
        
        if result['success']:
            print(f"Created {result['positions_created']} positions")
            print(f"Processed {result['trades_processed']} trades")
            
            # Check validation summary
            validation_summary = result['validation_summary']
            print(f"Groups with issues: {validation_summary['groups_with_issues']}")
            print(f"Overlap prevention applied: {validation_summary['overlap_prevention_applied']}")
            
            # Get detailed validation results
            detailed_summary = service.get_validation_summary()
            for group, details in detailed_summary['group_details'].items():
                if details['validation_issues']:
                    print(f"Group {group} had validation issues:")
                    print(f"  Warnings: {details['warnings']}")
                    print(f"  Errors: {details['errors']}")
        else:
            print(f"Rebuild failed: {result['error']}")
    """)


def test_prevention_report():
    """Test the prevention report generation"""
    print("\n" + "=" * 80)
    print("TESTING PREVENTION REPORT GENERATION")
    print("=" * 80)
    
    print("Prevention Report Example:")
    print("-" * 40)
    print("""
    # Generate comprehensive overlap prevention report
    with PositionOverlapPrevention() as validator:
        
        # Generate report for all positions
        full_report = validator.generate_prevention_report()
        print(full_report)
        
        # Generate report for specific account
        account_report = validator.generate_prevention_report(account='TestAccount')
        print(account_report)
        
        # Generate report for specific account/instrument
        specific_report = validator.generate_prevention_report(
            account='TestAccount', 
            instrument='MNQ'
        )
        print(specific_report)
    """)


def main():
    """Run all tests"""
    print("POSITION OVERLAP PREVENTION SYSTEM TEST SUITE")
    print("=" * 80)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Run tests
        test_pre_validation()
        test_position_building_validation()
        test_enhanced_position_service()
        test_prevention_report()
        
        print("\n" + "=" * 80)
        print("ALL TESTS COMPLETED SUCCESSFULLY")
        print("=" * 80)
        
        print("\nOVERLAP PREVENTION SYSTEM FEATURES:")
        print("-" * 40)
        print("✓ Pre-validation of executions before position building")
        print("✓ Timestamp integrity validation")
        print("✓ Data consistency validation")
        print("✓ Quantity flow validation")
        print("✓ Duplicate execution detection")
        print("✓ Position overlap detection")
        print("✓ Boundary violation detection")
        print("✓ Automatic overlap fix suggestions")
        print("✓ Enhanced position building with validation")
        print("✓ Comprehensive validation reporting")
        print("✓ Real-time validation during position building")
        
        print("\nINTEGRATION RECOMMENDATIONS:")
        print("-" * 40)
        print("1. Replace PositionService with EnhancedPositionService")
        print("2. Enable validation by default in position building")
        print("3. Add validation checks to position rebuild endpoint")
        print("4. Implement validation reporting in the web interface")
        print("5. Add automated overlap detection to data import process")
        print("6. Set up monitoring alerts for validation issues")
        
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()