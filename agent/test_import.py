import traceback
import sys

try:
    from app.api.routes import ingest
    print("ALL IMPORTS OK")
except Exception as e:
    traceback.print_exc()
    print(f"\n\nERROR TYPE: {type(e).__name__}")
    print(f"ERROR MSG: {e}")
