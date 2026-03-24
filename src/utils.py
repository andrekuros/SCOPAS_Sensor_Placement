"""
Utility functions for the framework.
"""

import sys
from datetime import datetime


def print_flush(message, **kwargs):
    """
    Print with automatic flush for real-time output in nohup/redirected files.
    
    Usage:
        print_flush("Processing...")
        print_flush(f"Progress: {i}/{total}")
    
    Args:
        message: Message to print
        **kwargs: Additional arguments for print()
    """
    print(message, flush=True, **kwargs)


def print_header(title, width=80, char='='):
    """Print a formatted header with flush."""
    print_flush('\n' + char * width)
    print_flush(title.center(width))
    print_flush(char * width)


def print_progress(current, total, prefix='', suffix='', decimals=1, length=50):
    """
    Print progress bar with flush.
    
    Args:
        current: Current iteration
        total: Total iterations
        prefix: Prefix string
        suffix: Suffix string
        decimals: Positive number of decimals in percent complete
        length: Character length of bar
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (current / float(total)))
    filled_length = int(length * current // total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    print_flush(f'\r{prefix} |{bar}| {percent}% {suffix}', end='')
    if current == total:
        print_flush()  # New line on complete


def timestamp():
    """Get current timestamp string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def print_timestamped(message):
    """Print message with timestamp."""
    print_flush(f"[{timestamp()}] {message}")


