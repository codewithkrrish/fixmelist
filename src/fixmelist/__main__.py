"""Allow `python -m fixmelist` as well as the installed console script."""

from .cli import entry

if __name__ == "__main__":
    entry()
