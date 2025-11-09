#!/usr/bin/env python3
"""
DSMF Vətəndaş Müraciət Botu - İşə Salma Skripti
"""
import sys
import os

# src qovluğunu path-ə əlavə et
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from bot import main
try:
    from version import __version__
except Exception:
    __version__ = "0.0.0"

if __name__ == "__main__":
    print(f"DSMF Müraciət Botu işə salınır... v{__version__}")
    main()
