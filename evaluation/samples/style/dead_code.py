import os
import sys  # BUG: Unused import
import json  # BUG: Unused import

DEBUG = False


def process(data):
    result = transform(data)
    # BUG: Unreachable code after return
    return result
    print("Done processing")
    cleanup()


def old_function():
    # BUG: Deprecated function still in codebase
    pass
