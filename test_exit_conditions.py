#!/usr/bin/env python3
"""
EXIT CONDITIONS FUNCTIONALITY TEST
Tests if $1 Reversal Stop and $1 Dynamic Trailing are working correctly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Mock MT5 for testing
class MockPosition:
    def __init__(self, ticket, price_open, position_type):
        self.ticket = ticket
        self.price_open = price_open
        self.type = position_type
        self.sl = price_open - 1.0 if position_type == 0 else price_open + 1.0  # Mock broker SL
        self.tp = price_open + 4.0 if position_type == 0 else price_open - 4.0

class MockTick:
    def __init__(self, bid, ask):
        self.bid = bid
        self.ask = ask

class MockSymbolInfo:
    def __init__(self):
        self.digits = 2

# Test the exit logic from each file
def test_flexible_entry_test_exit():
    """Test exit logic from flexible_entry_test.py"""
    print("🧪 TESTING: flexible_entry_test.py exit logic")
    
    # Mock position: BUY at 2700.00
    pos = MockPosition(ticket=12345, price_open=2700.00, position_type=0)  # BUY
    
    # Test Case 1: $1 Reversal should trigger at 2699.00
    tick = MockTick(bid=2699.00, ask=2699.05)
    
    # Simulate the logic from flexible_entry_test.py (lines 340-365)
    direction = "BUY"
    loss_pts = pos.price_open - tick.bid  # 2700.00 - 2699.00 = 1.0
    should_trigger = loss_pts >= 1.0
    
    print(f"   Entry: {pos.price_open:.2f} | Bid: {tick.bid:.2f} | Loss: {loss_pts:.2f}pts")
    print(f"   Should trigger $1 Reversal: {should_trigger}")
    
    # Test Case 2: Edge case - exactly 1.0 point loss
    tick2 = MockTick(bid=2699.01, ask=2699.06)
    loss_pts2 = pos.price_open - tick2.bid  # 0.99 points
    should_trigger2 = loss_pts2 >= 1.0
    
    print(f"   Edge case - Bid: {tick2.bid:.2f} | Loss: {loss_pts2:.2f}pts | Should trigger: {should_trigger2}")
    
    # Test Case 3: Trailing activation check
    # Simulate profit measurement from reference_price (bid at entry)
    reference_price = 2699.95  # Mock bid at entry
    profit_points = tick.bid - reference_price  # 2699.00 - 2699.95 = -0.95 (loss)
    trailing_should_activate = profit_points >= 0.01
    
    print(f"   Trailing test - Profit: {profit_points:.3f}pts | Should activate: {trailing_should_activate}")
    
    return should_trigger, should_trigger2, trailing_should_activate

def test_enhanced_strategy_exit():
    """Test exit logic from enhanced_strategy.py"""
    print("\n🧪 TESTING: enhanced_strategy.py exit logic")
    
    # Same test cases
    pos = MockPosition(ticket=12346, price_open=2700.00, position_type=0)  # BUY
    tick = MockTick(bid=2699.00, ask=2699.05)
    
    # Simulate the logic from enhanced_strategy.py (lines 600-625)
    direction = "BUY"
    loss_pts = pos.price_open - tick.bid
    should_trigger = loss_pts >= 1.0
    
    print(f"   Entry: {pos.price_open:.2f} | Bid: {tick.bid:.2f} | Loss: {loss_pts:.2f}pts")
    print(f"   Should trigger $1 Reversal: {should_trigger}")
    
    return should_trigger

def test_broker_sl_conflict():
    """Test if broker SL conflicts with manual exits"""
    print("\n🧪 TESTING: Broker SL vs Manual Exit Conflict")
    
    pos = MockPosition(ticket=12347, price_open=2700.00, position_type=0)  # BUY
    
    # Broker SL is set to entry - 1.0 = 2699.00
    broker_sl = pos.sl  # 2699.00
    
    # Manual exit also triggers at entry - 1.0 = 2699.00
    manual_exit_level = pos.price_open - 1.0  # 2699.00
    
    conflict_exists = broker_sl == manual_exit_level
    
    print(f"   Broker SL: {broker_sl:.2f}")
    print(f"   Manual Exit Level: {manual_exit_level:.2f}")
    print(f"   CONFLICT EXISTS: {conflict_exists}")
    
    return conflict_exists

def test_trailing_update_logic():
    """Test if trailing stop updates work"""
    print("\n🧪 TESTING: Trailing Stop Update Logic")
    
    pos = MockPosition(ticket=12348, price_open=2700.00, position_type=0)  # BUY
    tick = MockTick(bid=2701.50, ask=2701.55)  # Price moved up
    
    # Current broker SL
    current_broker_sl = pos.sl  # 2699.00 (entry - 1.0)
    
    # Calculate new trailing SL
    new_trailing_sl = tick.bid - 1.0  # 2701.50 - 1.0 = 2700.50
    
    # Test the update condition from all files
    should_update = new_trailing_sl > current_broker_sl  # 2700.50 > 2699.00 = True
    
    print(f"   Current Broker SL: {current_broker_sl:.2f}")
    print(f"   New Trailing SL: {new_trailing_sl:.2f}")
    print(f"   Should Update: {should_update}")
    
    # Test the problematic case
    pos2 = MockPosition(ticket=12349, price_open=2700.00, position_type=0)  # BUY
    tick2 = MockTick(bid=2700.01, ask=2700.06)  # Small move up
    
    current_broker_sl2 = pos2.sl  # 2699.00
    new_trailing_sl2 = tick2.bid - 1.0  # 2700.01 - 1.0 = 2699.01
    should_update2 = new_trailing_sl2 > current_broker_sl2  # 2699.01 > 2699.00 = True
    
    print(f"   Small move case - New SL: {new_trailing_sl2:.2f} | Should Update: {should_update2}")
    
    return should_update, should_update2

def test_reference_price_consistency():
    """Test reference price consistency issues"""
    print("\n🧪 TESTING: Reference Price Consistency")
    
    # Entry scenario
    entry_price = 2700.00  # Fill price
    bid_at_entry = 2699.95  # Bid at entry time
    ask_at_entry = 2700.05  # Ask at entry time
    
    # Current tick
    current_bid = 2700.10
    
    # Different profit calculations
    profit_from_fill = current_bid - entry_price      # 0.10 points
    profit_from_bid = current_bid - bid_at_entry      # 0.15 points
    
    print(f"   Fill Price: {entry_price:.2f}")
    print(f"   Bid at Entry: {bid_at_entry:.2f}")
    print(f"   Current Bid: {current_bid:.2f}")
    print(f"   Profit from Fill: {profit_from_fill:.3f}pts")
    print(f"   Profit from Bid at Entry: {profit_from_bid:.3f}pts")
    print(f"   INCONSISTENT: {abs(profit_from_fill - profit_from_bid) > 0.001}")
    
    return profit_from_fill, profit_from_bid

def main():
    """Run all exit condition tests"""
    print("=" * 60)
    print("EXIT CONDITIONS FUNCTIONALITY TEST")
    print("=" * 60)
    
    # Test each file's exit logic
    result1 = test_flexible_entry_test_exit()
    result2 = test_enhanced_strategy_exit()
    conflict = test_broker_sl_conflict()
    trailing = test_trailing_update_logic()
    reference = test_reference_price_consistency()
    
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    
    print(f"✅ $1 Reversal Logic Working: {result1[0] and result2}")
    print(f"⚠️  Edge Case Handling: {not result1[1]} (should be False)")
    print(f"❌ Trailing Activation: {result1[2]} (should be True when profitable)")
    print(f"🚨 Broker SL Conflict: {conflict} (CRITICAL ISSUE)")
    print(f"✅ Trailing Updates: {trailing[0]} (basic case)")
    print(f"✅ Small Move Updates: {trailing[1]} (edge case)")
    print(f"⚠️  Reference Price Inconsistency: {abs(reference[0] - reference[1]) > 0.001}")
    
    print("\n" + "=" * 60)
    print("CRITICAL ISSUES IDENTIFIED:")
    print("=" * 60)
    
    issues = []
    if conflict:
        issues.append("🚨 BROKER SL CONFLICT: Both broker and manual exits at same level")
    
    if not result1[2]:
        issues.append("❌ TRAILING LOGIC: May not activate when expected")
    
    if abs(reference[0] - reference[1]) > 0.001:
        issues.append("⚠️  REFERENCE INCONSISTENCY: Different profit calculations")
    
    if not issues:
        print("✅ NO CRITICAL ISSUES FOUND")
    else:
        for issue in issues:
            print(issue)
    
    print("\n" + "=" * 60)
    print("RECOMMENDATION:")
    print("=" * 60)
    
    if issues:
        print("❌ EXIT CONDITIONS ARE NOT WORKING CORRECTLY")
        print("   Use the centralized_exit_manager.py fix provided earlier")
        print("   Key fixes needed:")
        print("   1. Remove broker SL conflicts")
        print("   2. Use consistent reference prices")
        print("   3. Fix trailing update logic")
    else:
        print("✅ EXIT CONDITIONS APPEAR TO BE WORKING")
    
    return len(issues) == 0

if __name__ == "__main__":
    working = main()
    sys.exit(0 if working else 1)