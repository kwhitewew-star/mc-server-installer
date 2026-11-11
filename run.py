"""Start MC Server Installer:  python run.py   (same as: python -m mcsi)"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcsi.ui.main_window import main  # noqa: E402

main()
