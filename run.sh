#!/bin/bash
set -e
which python
python -m pip install -q -r requirements.txt
python app_minimal.py
