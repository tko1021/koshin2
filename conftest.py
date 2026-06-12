"""pytest 用: リポジトリルートを import パスに追加して `import dips` を可能にする。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
