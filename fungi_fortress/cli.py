"""Command-line interface entry point for Fungi Fortress."""
import sys
import curses
import traceback
import os
from datetime import datetime


def main():
    """Entry point for the fungi console command."""
    # Add parent directory to path to import main.py from repo root
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    from main import main as game_main
    
    try:
        curses.wrapper(game_main)
    except Exception as e:
        # Ensure curses cleanup happens
        try:
            curses.endwin()
        except:
            pass
        
        # Write full traceback to crash log
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        crash_log_path = os.path.join(log_dir, "fungi_crash.log")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tb_str = traceback.format_exc()
        
        with open(crash_log_path, "a") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"CRASH at {timestamp}\n")
            f.write(f"{'='*80}\n")
            f.write(tb_str)
            f.write(f"\n{'='*80}\n\n")
        
        # Print error info to stderr after curses ends
        print(f"\n{'='*80}", file=sys.stderr)
        print(f"FATAL ERROR: {e}", file=sys.stderr)
        print(f"{'='*80}", file=sys.stderr)
        print(f"\nFull crash log written to: {crash_log_path}", file=sys.stderr)
        print("\nLast traceback frames:", file=sys.stderr)
        print("".join(traceback.format_tb(sys.exc_info()[2])[-3:]), file=sys.stderr)
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        print(f"{'='*80}\n", file=sys.stderr)
        
        sys.exit(1)


if __name__ == "__main__":
    main()
