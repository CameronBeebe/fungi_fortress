#!/usr/bin/env python3
"""Startup smoke test to catch initialization regressions."""

import pytest
from unittest.mock import MagicMock, patch


def test_app_startup_smoke():
    """Test that app.game_loop doesn't crash on startup.
    
    Catches regressions like:
    - Round-2: AttributeError: 'LLMConfig' object has no attribute 'provider' at app.py:65
    - Missing _handle_action attribute
    
    Calls actual app.game_loop with mocked curses that returns ESC to quit immediately.
    """
    from fungi_fortress import app
    
    # Create a mock stdscr that returns ESC on getch
    mock_stdscr = MagicMock()
    mock_stdscr.getmaxyx.return_value = (40, 120)
    mock_stdscr.timeout.return_value = None
    mock_stdscr.nodelay.return_value = None
    mock_stdscr.getch.return_value = 27  # ESC key
    
    # Mock curses functions
    with patch('curses.set_escdelay'), \
         patch('curses.curs_set'), \
         patch('curses.start_color'), \
         patch('curses.use_default_colors'), \
         patch('curses.init_pair'), \
         patch('curses.color_pair', return_value=0), \
         patch('curses.newwin', return_value=mock_stdscr):
        
        try:
            # Call the actual game_loop - it should initialize everything and then
            # immediately quit when getch returns ESC
            game_logic, input_handler = app.game_loop(mock_stdscr)
            
            # Verify it initialized successfully
            assert game_logic is not None
            assert input_handler is not None
            assert game_logic.game_state is not None
            
            print("✓ App startup smoke test passed")
            print(f"  - app.game_loop completed without crash")
            print(f"  - GameLogic and InputHandler initialized")
            
        except AttributeError as e:
            if "'LLMConfig' object has no attribute 'provider'" in str(e):
                pytest.fail(f"Startup crashed with provider attribute error (round-2 regression): {e}")
            elif "_handle_action" in str(e):
                pytest.fail(f"Startup crashed with missing _handle_action: {e}")
            else:
                pytest.fail(f"Startup crashed with AttributeError: {e}")
        except Exception as e:
            pytest.fail(f"Startup crashed with unexpected error: {e}")


def test_app_module_imports():
    """Test that app module imports without errors."""
    try:
        # This will catch import-time errors
        from fungi_fortress import app
        
        # Verify the main function exists
        assert hasattr(app, 'main')
        
        print("✓ app module imports successfully")
        
    except ImportError as e:
        pytest.fail(f"Failed to import app: {e}")
    except Exception as e:
        pytest.fail(f"Unexpected error importing app: {e}")


if __name__ == "__main__":
    test_app_startup_smoke()
    test_app_module_imports()
    print("\nAll startup smoke tests passed!")
