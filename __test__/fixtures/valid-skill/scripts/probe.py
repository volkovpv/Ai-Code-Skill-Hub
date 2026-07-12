#!/usr/bin/env python3
"""Print the execution context as JSON: cwd and visible environment keys.

The test suite runs this script in a temporary directory with a sanitized
environment and asserts that no secrets leak into skill scripts.
"""

import json
import os

print(json.dumps({"cwd": os.getcwd(), "env_keys": sorted(os.environ.keys())}))
