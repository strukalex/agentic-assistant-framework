"""Telegram Bot - ABSOLUTE MINIMAL TEST.

Just returns immediately to test if worker hangs.
"""

print('hello')

def main(test_param: str = "hello") -> dict:
    print('main')
    """Absolute minimal test - just return immediately."""
    return {"status": "ok", "received": test_param}
