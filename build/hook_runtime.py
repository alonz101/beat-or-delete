import os
import sys

# When running as a PyInstaller one-file bundle, extracted files live in
# sys._MEIPASS. Prepend it to PATH so bundled ffprobe is found by subprocess.
if hasattr(sys, '_MEIPASS'):
    os.environ['PATH'] = sys._MEIPASS + os.pathsep + os.environ.get('PATH', '')
