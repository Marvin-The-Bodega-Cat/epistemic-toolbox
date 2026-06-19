#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from epistemic_toolbox.concept_equivalence import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
