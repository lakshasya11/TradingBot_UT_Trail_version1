# Tick Confirmation Configuration
# Adjust these values to change confirmation requirements

# Number of consecutive ticks needed to confirm a signal (5-7 recommended)
REQUIRED_CONFIRMATIONS = 2

# Time window in seconds to collect confirmations (10-15 recommended)
CONFIRMATION_WINDOW = 10

# To change to 7-tick confirmation, simply change REQUIRED_CONFIRMATIONS to 7
# To make it faster (3-tick), change to 3
# To make it slower (10-tick), change to 10

print(f"Tick Confirmation Config: {REQUIRED_CONFIRMATIONS} ticks in {CONFIRMATION_WINDOW} seconds")