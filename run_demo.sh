#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python3 analyze_orders.py sample_orders.csv --out my_report --demo
printf '\nDashboard ready at: %s/my_report/dashboard.html\n' "$PWD"
