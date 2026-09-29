"""
Asegura que la raiz del proyecto este en sys.path para poder importar `app`
sin depender de como se invoque pytest (uv run pytest, pytest a secas, IDE).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
