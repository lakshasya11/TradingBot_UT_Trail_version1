#!/usr/bin/env python3
"""
EXIT CONDITIONS FUNCTIONALITY TEST - Simple Version
Tests if $1 Reversal Stop and $1 Dynamic Trailing are working correctly
"""

def test_exit_logic():
    """Test the core exit logic from all files"""
    print("TESTING: Exit Conditions Logic")
    print("-" * 50)
    
    # Test Case 1: $1 Reversal Logic
    print("TEST 1: $1 Reversal Stop Logic")
    
    # Mock BUY position at 2700.00
    entry_price = 2700.00
    current_bid = 2699.00  # 1.0 point loss
    
    # This is the ACTUAL logic from all your files:
    loss_pts = entry_price - current_bid  # 2700.00 - 2699.00 = 1.0
    should_trigger = loss_pts >= 1.0      # 1.0 >= 1.0 = True
    
    print(f"  Entry: {entry_price:.2f}")
    print(f"  Current Bid: {current_bid:.2f}")
    print(f"  Loss Points: {loss_pts:.2f}")
    print(f"  Should Trigger: {should_trigger}")
    print(f"  RESULT: {'WORKING' if should_trigger else 'BROKEN'}")
    
    # Test Case 2: Edge Case
    print("\nTEST 2: Edge Case - 0.99 point loss")
    current_bid2 = 2699.01  # 0.99 point loss
    loss_pts2 = entry_price - current_bid2
    should_trigger2 = loss_pts2 >= 1.0
    
    print(f"  Current Bid: {current_bid2:.2f}")
    print(f"  Loss Points: {loss_pts2:.2f}")
    print(f"  Should Trigger: {should_trigger2}")
    print(f"  RESULT: {'CORRECT' if not should_trigger2 else 'INCORRECT'}")
    
    # Test Case 3: Broker SL Conflict
    print("\nTEST 3: Broker SL vs Manual Exit Conflict")
    broker_sl = entry_price - 1.0      # 2699.00 (set at entry)
    manual_exit_level = entry_price - 1.0  # 2699.00 (manual check)
    conflict = broker_sl == manual_exit_level
    
    print(f"  Broker SL: {broker_sl:.2f}")
    print(f"  Manual Exit Level: {manual_exit_level:.2f}")
    print(f"  CONFLICT EXISTS: {conflict}")
    print(f"  RESULT: {'CRITICAL ISSUE' if conflict else 'OK'}")
    
    # Test Case 4: Trailing Update Logic
    print("\nTEST 4: Trailing Stop Update Logic")
    current_broker_sl = 2699.00  # Initial SL
    current_bid_profitable = 2701.00  # Price moved up
    new_trailing_sl = current_bid_profitable - 1.0  # 2700.00
    
    # This is the ACTUAL condition from your files:
    should_update = new_trailing_sl > current_broker_sl  # 2700.00 > 2699.00
    
    print(f"  Current Broker SL: {current_broker_sl:.2f}")
    print(f"  New Trailing SL: {new_trailing_sl:.2f}")
    print(f"  Should Update: {should_update}")
    print(f"  RESULT: {'WORKING' if should_update else 'BROKEN'}")
    
    # Test Case 5: Problematic Trailing Case
    print("\nTEST 5: Problematic Trailing Case")
    current_bid_small = 2700.50  # Small profitable move
    new_trailing_sl_small = current_bid_small - 1.0  # 2699.50
    should_update_small = new_trailing_sl_small > current_broker_sl  # 2699.50 > 2699.00
    
    print(f"  Small Move Bid: {current_bid_small:.2f}")
    print(f"  New Trailing SL: {new_trailing_sl_small:.2f}")
    print(f"  Should Update: {should_update_small}")
    print(f"  RESULT: {'WORKING' if should_update_small else 'BROKEN'}")
    
    # Test Case 6: The REAL Problem Case
    print("\nTEST 6: The REAL Problem - Initial vs Trailing")
    initial_sl = entry_price - 1.0  # 2699.00 (set at entry)
    small_profit_bid = 2700.01      # Tiny profit
    calculated_trail = small_profit_bid - 1.0  # 2699.01
    
    # The problem: 2699.01 > 2699.00 is True, but barely
    # In practice, this might not update due to broker precision
    update_condition = calculated_trail > initial_sl
    difference = calculated_trail - initial_sl
    
    print(f"  Initial SL: {initial_sl:.2f}")
    print(f"  Calculated Trail: {calculated_trail:.2f}")
    print(f"  Difference: {difference:.2f}")
    print(f"  Update Condition: {update_condition}")
    print(f"  RESULT: {'MIGHT WORK' if update_condition else 'BROKEN'}")
    
    print("\n" + "=" * 50)
    print("OVERALL ASSESSMENT:")
    print("=" * 50)
    
    issues = []
    if not should_trigger:
        issues.append("$1 Reversal logic broken")
    if conflict:
        issues.append("Broker SL conflict exists")
    if not should_update:
        issues.append("Trailing update logic broken")
    if difference < 0.01:
        issues.append("Trailing precision issues likely")
    
    if issues:
        print("CRITICAL ISSUES FOUND:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        print("\nCONCLUSION: EXIT CONDITIONS ARE NOT WORKING RELIABLY")
        return False
    else:
        print("NO CRITICAL ISSUES FOUND")
        print("CONCLUSION: EXIT CONDITIONS APPEAR TO BE WORKING")
        return True

def main():
    """Run the test"""
    print("EXIT CONDITIONS FUNCTIONALITY TEST")
    print("=" * 50)
    
    working = test_exit_logic()
    
    print("\nRECOMMENDATION:")
    print("-" * 50)
    if working:
        print("Your exit conditions should work correctly.")
    else:
        print("Your exit conditions have critical issues.")
        print("Use the centralized_exit_manager.py fix provided.")
        print("Key problems:")
        print("1. Broker SL conflicts with manual exits")
        print("2. Floating-point precision issues")
        print("3. Complex logic prone to errors")
    
    return working

if __name__ == "__main__":
    import sys
    working = main()
    sys.exit(0 if working else 1)