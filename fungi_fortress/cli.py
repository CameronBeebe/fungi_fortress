"""Command-line interface entry point for Fungi Fortress."""
import sys
import os

def main():
    """Entry point for the fungi console command."""
    # Add parent directory to path to import main.py from repo root
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    import curses
    from main import main as game_main
    
    try:
        curses.wrapper(game_main)
    except Exception as e:
        import logging
        logging.exception("Unhandled exception in curses.wrapper or main function.")
        print(f"FATAL ERROR: {e}", file=sys.stderr)
        logging.shutdown()
        sys.exit(1)

if __name__ == "__main__":
    main()
