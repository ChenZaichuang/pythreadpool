#!/bin/bash
set -e

python3 setup.py sdist
twine upload dist/*.tar.gz