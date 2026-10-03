# Message Display Verification

## Question
Do the bridge refusal and cancellation messages actually show on the game screen, or do they only land in the log file?

## Answer: Messages ARE Visible on Screen

### Evidence

1. **Message Route**: 
   - Messages use `game_state.add_debug_message()` 
   - Located at `fungi_fortress/game_state.py:258-269`

2. **Display Implementation** (`game_state.py:258-269`):
   ```python
   def add_debug_message(self, msg: str) -> None:
       """Adds a debug/info message visible to the player in-game."""
       game_logic_logger.info(msg)  # Also logs to file
       shown = msg if len(msg) <= 100 else msg[:97] + "..."
       self.debug_log.append(shown)  # Add to on-screen queue
       if len(self.debug_log) > 8:
           self.debug_log.pop(0)  # Keep last 8 messages
   ```

3. **Renderer Integration** (`renderer.py:485-494`):
   ```python
   # --- Render Log ---
   log_h, log_w = LOG_HEIGHT, MAP_WIDTH  # LOG_HEIGHT = 5
   start_line = max(0, len(self.game_state.debug_log) - log_h)
   for i, msg in enumerate(self.game_state.debug_log[start_line:]):
       if i < log_h:
           self.log_win.addstr(i, 0, msg.ljust(log_w-1))
   ```

4. **Screen Layout**:
   - The log window displays at the bottom of the game screen
   - Shows the last 5 messages from `debug_log`
   - Messages scroll as new ones arrive

## Messages Confirmed Visible

### Bridge Refusal Message
**Location**: `input_handler.py:~630`
```python
self.game_state.add_debug_message(
    f"Cannot queue bridge: need {BRIDGE_WOOD_COST} wood, "
    f"have {total_wood} total ({available_wood} available, "
    f"{reserved_wood} reserved for other bridges)"
)
```
**Shows**: "Cannot queue bridge: need 1 wood, have 0 total (0 available, 0 reserved for other bridges)"

### Bridge Cancellation Message
**Location**: `game_logic.py:~1395`
```python
self.game_state.add_debug_message(
    f"Bridge at {failed_bridge_pos} failed ({reason}). "
    f"Cancelled {len(cancelled_tasks)} dependent bridge(s) at: {positions}"
)
```
**Shows**: "Bridge at (1,0) failed (insufficient wood). Cancelled 2 dependent bridge(s) at: (2,0), (3,0)"

## Conclusion
✅ Both refusal and cancellation messages are displayed on-screen in the log window
✅ They are also logged to the file for debugging
✅ No changes needed - messages are already player-visible
