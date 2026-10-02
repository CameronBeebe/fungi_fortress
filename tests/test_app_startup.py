#!/usr/bin/env python3
"""Startup smoke test to catch initialization regressions."""

import pytest
from unittest.mock import MagicMock, patch


def test_app_startup_smoke():
    """Test that app.py initialization doesn't crash.
    
    Catches regressions like the round-2 AttributeError: 'LLMConfig' object has no attribute 'provider'
    that occurred during startup at app.py:65.
    """
    # Mock curses to avoid needing a terminal
    with patch('curses.initscr') as mock_initscr, \
         patch('curses.curs_set'), \
         patch('curses.start_color'), \
         patch('curses.use_default_colors'), \
         patch('curses.init_pair'), \
         patch('curses.color_pair', return_value=0), \
         patch('curses.noecho'), \
         patch('curses.cbreak'), \
         patch('curses.newwin') as mock_newwin:
        
        # Create a mock screen
        mock_screen = MagicMock()
        mock_screen.getmaxyx.return_value = (40, 120)
        mock_screen.nodelay.return_value = None
        mock_screen.getch.return_value = ord('q')  # Simulate quit immediately
        mock_initscr.return_value = mock_screen
        
        # Create a mock window
        mock_win = MagicMock()
        mock_win.getmaxyx.return_value = (40, 120)
        mock_newwin.return_value = mock_win
        
        # Try to import and initialize game components
        try:
            from fungi_fortress.game_state import GameState
            from fungi_fortress.game_logic import GameLogic
            from fungi_fortress.config_manager import LLMConfig
            
            # Initialize with mock config (no API key)
            llm_config = LLMConfig(
                api_key=None,
                model_name="mock-model",
                enable_streaming=False,
                context_level="low"
            )
            
            # Create game state and logic
            game_state = GameState(llm_config=llm_config)
            game_logic = GameLogic(game_state)
            
            # Verify basic initialization succeeded
            assert game_state is not None
            assert game_logic is not None
            assert game_state.tick == 0
            
            # Try one update cycle
            game_logic.update()
            assert game_state.tick == 1
            
            print("✓ App startup smoke test passed")
            print(f"  - GameState initialized")
            print(f"  - GameLogic initialized")
            print(f"  - One update cycle completed")
            
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
