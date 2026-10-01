"""Entry point for running fungi_fortress as a module.

This allows running the game with:
    python -m fungi_fortress
"""
import sys
import os

# Add the parent directory to sys.path to import main.py from root
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

if __name__ == "__main__":
    import curses
    from main import main
    
    try:
        curses.wrapper(main)
    except Exception as e:
        import logging
        logging.exception("Unhandled exception in curses.wrapper or main function.")
        print(f"FATAL ERROR: {e}", file=sys.stderr)
        logging.shutdown()
        sys.exit(1)
