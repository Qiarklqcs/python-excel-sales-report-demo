#!/usr/bin/env python3
"""Offline small-retailer CSV reporting. Python standard library only.

Sample: python analyze_orders.py sample_orders.csv --out my_report --demo
Real anonymized data: python analyze_orders.py my_orders.csv --out my_report
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

FIELDS = ['order_id', 'date', 'product', 'category', 'quantity', 'unit_price', 'unit_cost', 'status']
STATUSES = {'Completed', 'Refunded', 'Cancelled'}
CENT = Decimal('0.01')
ISO_DAY = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def cash(amount):
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def safe_csv_cell(value):
    """Disable spreadsheet evaluation on values sourced from CSV text."""
    text = str(value)
    if text.lstrip().startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n')):
        return "'" + text
    return text


def write_csv(path, headers, rows, *, text_columns=()):
    text_columns = set(text_columns)
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            writer.writerow([safe_csv_cell(item) if headers[i] in text_columns else item
                             for i, item in enumerate(row)])


def fmt_cad(value):
    return f'${value:,.2f}'


def html_dashboard(stats, *, demo):
    """Build a self-contained report with no CDNs, scripts, or remote requests."""
    esc = lambda s: html.escape(str(s), quote=True)
    total_rev = stats['revenue']
    total_profit = stats['gross_profit']
    margins = (total_profit / total_rev * 100) if total_rev else Decimal('0')
    months = stats['months']
    products = stats['products']
    scale = max((float(entry['revenue']) for _, entry in months), default=0) or 1
    month_blocks = ''.join(
        f'<div class="bar-row"><div class="bar-label">{esc(month)}</div>'
        f'<div class="bar-track"><div class="bar" style="width:{float(item["revenue"])/scale*100:.2f}%"></div></div>'
        f'<div class="bar-amount">{fmt_cad(item["revenue"])}</div></div>'
        for month, item in months
    ) or '<p>No accepted records.</p>'
    product_rows = ''.join(
        '<tr><td>' + esc(product) + '</td><td>' + esc(category) + '</td><td class="num">' + str(item['units']) +
        '</td><td class="num">' + fmt_cad(item['revenue']) + '</td><td class="num">' +
        fmt_cad(item['profit']) + '</td></tr>'
        for (product, category), item in products[:15]
    ) or '<tr><td colspan="5">No completed sales.</td></tr>'
    monthly_rows = ''.join(
        f'<tr><td>{esc(m)}</td><td class="num">{d["completed"]}</td>'
        f'<td class="num">{d["refunded"]}</td><td class="num">{d["cancelled"]}</td>'
        f'<td class="num">{fmt_cad(d["revenue"])}</td>'
        f'<td class="num">{fmt_cad(d["profit"])}</td></tr>' for m,d in months
    )
    alert = 'DEMO · FICTIONAL ORDERS' if demo else 'LOCAL REPORT · VERIFY BEFORE USE'
    source_label = esc(stats['source_name'])
    today = esc(datetime.now().strftime('%Y-%m-%d %H:%M'))
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sales Performance | Local Report</title><style>
:root{--navy:#11294b;--blue:#2563eb;--muted:#687589;--line:#e0e7ef;--bg:#f3f6fb;--white:#fff;--teal:#087e78}
*{box-sizing:border-box}body{font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;background:var(--bg);color:#142743;margin:0}
main{max-width:1120px;margin:auto;padding:36px 22px 62px}header{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap;align-items:flex-start;margin-bottom:24px}
.eyebrow{color:var(--blue);font-size:12px;letter-spacing:.13em;text-transform:uppercase;font-weight:800;margin:0 0 4px}h1{font-size:clamp(25px,3vw,34px);line-height:1.2;margin:0 0 9px;color:var(--navy)}p.sub{margin:0;color:var(--muted)}.pill{background:#e5f0ff;color:#164a9b;border:1px solid #c6dafe;border-radius:99px;padding:8px 13px;font-size:12px;font-weight:750;letter-spacing:.03em}
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:22px 0}.kpi,.panel{background:var(--white);border:1px solid var(--line);border-radius:14px;box-shadow:0 2px 10px #14274309}
.kpi{padding:23px}.kpi span{font-size:12px;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:.045em}.kpi strong{display:block;margin:9px 0 5px;font-size:27px;letter-spacing:-.04em;line-height:1.15;color:var(--navy)}.kpi small{color:var(--muted);font-size:12px}
.grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,.85fr);gap:16px}.panel{padding:22px;margin-bottom:16px;min-width:0}.panel h2{font-size:18px;margin:0 0 5px;color:var(--navy)}.hint{font-size:12px;color:var(--muted);margin:0 0 19px}
.bar-row{display:grid;grid-template-columns:68px minmax(50px,1fr) 94px;align-items:center;gap:10px;margin:14px 0}.bar-label{font-size:12px;font-weight:700;color:#4d617c}.bar-track{height:17px;background:#edf2f9;border-radius:5px;overflow:hidden}.bar{height:100%;background:linear-gradient(90deg,#3375ef,#5da5fd);border-radius:5px}.bar-amount{text-align:right;font-size:12px;font-weight:700;color:#405371}
.three{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:25px}.mini{border-left:3px solid #d5e3f7;padding-left:10px}.mini strong{display:block;font-size:21px}.mini span{display:block;font-size:11px;color:var(--muted)}
.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;white-space:nowrap;font-size:13px}th{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#607086;background:#f3f6fb}td,th{padding:12px 10px;border-bottom:1px solid var(--line)}tr:last-child td{border-bottom:0}td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}a{color:#1356c5;text-decoration:none;font-weight:650}a:hover{text-decoration:underline}.downloads{display:flex;flex-wrap:wrap;gap:10px}.downloads a{border:1px solid #d6e4f4;padding:9px 12px;border-radius:9px;background:#f8fbff;font-size:12px}
.note{color:#65748c;font-size:12px;line-height:1.65;margin:5px 0}.status{color:var(--teal);font-weight:700}footer{margin-top:24px;font-size:12px;color:var(--muted)}@media(max-width:850px){.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.grid{grid-template-columns:1fr}}@media(max-width:480px){main{padding:22px 12px}.kpi{padding:16px}.kpi strong{font-size:23px}.bar-row{grid-template-columns:55px minmax(30px,1fr) 79px;gap:5px}.bar-label,.bar-amount{font-size:10px}.three{gap:4px}}
@media print{body{background:white}main{padding:0}.panel,.kpi{box-shadow:none}a{color:inherit}}
</style></head><body><main>
<header><div><p class="eyebrow">Sales Reporting Automation</p><h1>Sales Performance Dashboard</h1>
<p class="sub">Source: __SOURCE__ &nbsp;·&nbsp; Generated locally: __GENERATED__ &nbsp;·&nbsp; Currency: CAD</p></div><div class="pill">__BADGE__</div></header>
<section class="kpis"><div class="kpi"><span>Recognized sales</span><strong>__REV__</strong><small>Completed orders only</small></div>
<div class="kpi"><span>Gross profit</span><strong>__PROFIT__</strong><small>Sales less product cost</small></div>
<div class="kpi"><span>Completed orders</span><strong>__DONE__</strong><small>From __TOTAL__ accepted records</small></div>
<div class="kpi"><span>Gross margin</span><strong>__MARGIN__</strong><small>Before other operating expenses</small></div></section>
<div class="grid"><section class="panel"><h2>Monthly sales</h2><p class="hint">Completed-order revenue by calendar month</p>__MONTH_BARS__</section>
<section class="panel"><h2>Data quality and order status</h2><p class="hint">Simple reconciliation after validation</p>
<div class="three"><div class="mini"><strong>__REFUNDS__</strong><span>Fully refunded</span></div>
<div class="mini"><strong>__CANCELLED__</strong><span>Cancelled</span></div><div class="mini"><strong>__REJECTS__</strong><span>Rejected rows</span></div></div>
<p class="note" style="margin-top:26px">Accepted records: <span class="status">__TOTAL__</span>. Inspect quality_report.txt for row-level validation issues.</p>
<h2 style="margin-top:27px">Exported files</h2><div class="downloads"><a href="clean_orders.csv">Clean orders CSV</a><a href="monthly_summary.csv">Monthly CSV</a><a href="product_summary.csv">Product CSV</a><a href="quality_report.txt">Validation report</a></div></section></div>
<section class="panel"><h2>Product performance</h2><p class="hint">Top 15 products by recognized sales revenue, completed orders only</p>
<div class="table-wrap"><table><thead><tr><th>Product</th><th>Category</th><th class="num">Units</th><th class="num">Sales</th><th class="num">Gross profit</th></tr></thead>
<tbody>__PRODUCT_ROWS__</tbody></table></div></section>
<section class="panel"><h2>Monthly breakdown</h2><p class="hint">Consistent reconciliation with the downloadable monthly summary</p>
<div class="table-wrap"><table><thead><tr><th>Month</th><th class="num">Completed</th><th class="num">Refunded</th><th class="num">Cancelled</th><th class="num">Sales</th><th class="num">Gross profit</th></tr></thead><tbody>__MONTH_ROWS__</tbody></table></div></section>
<p class="note"><strong>Assumptions:</strong> All prices and costs are CAD. Only completed orders recognize sales/COGS. Refunded orders are treated as fully refunded and contribute zero recognized sales and product costs; cancelled orders likewise contribute zero. This is an operational reporting demo—not tax, inventory, financial statement, or accounting advice. Partial refunds, shipping, taxes, payment fees and multiple currencies are not supported.</p>
<footer>Offline report generated using Python standard library. No external resources, external scripts, or network requests.</footer></main></body></html>'''.replace('__SOURCE__', source_label).replace('__GENERATED__', today).replace('__BADGE__', esc(alert)).replace('__REV__', fmt_cad(total_rev)).replace('__PROFIT__', fmt_cad(total_profit)).replace('__DONE__', str(stats['completed'])).replace('__TOTAL__', str(stats['valid'])).replace('__MARGIN__', f'{margins:.1f}%').replace('__MONTH_BARS__', month_blocks).replace('__REFUNDS__', str(stats['refunded'])).replace('__CANCELLED__', str(stats['cancelled'])).replace('__REJECTS__', str(stats['rejected'])).replace('__PRODUCT_ROWS__', product_rows).replace('__MONTH_ROWS__', monthly_rows)


def build(input_path, out_dir, *, demo=False):
    input_path = Path(input_path)
    out_dir = Path(out_dir)
    if not input_path.is_file():
        raise FileNotFoundError(f'Input CSV not found: {input_path}')
    out_dir.mkdir(parents=True, exist_ok=True)
    accepted, errors, seen = [], [], set()
    with input_path.open('r', newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError('The CSV must include a header row.')
        missing = [field for field in FIELDS if field not in reader.fieldnames]
        if missing:
            raise ValueError('Missing required columns: ' + ', '.join(missing))
        for line, row in enumerate(reader, 2):
            try:
                if None in row:
                    raise ValueError('Too many columns or malformed CSV row')
                if any(row[field] is None for field in FIELDS):
                    raise ValueError('Missing required cell(s)')
                oid = row['order_id'].strip()
                if not oid or oid in seen:
                    raise ValueError('Missing or duplicate order_id')
                raw_date = row['date'].strip()
                if not ISO_DAY.fullmatch(raw_date):
                    raise ValueError('Date must use YYYY-MM-DD')
                when = date.fromisoformat(raw_date)
                product = row['product'].strip()
                category = row['category'].strip()
                if not product or not category:
                    raise ValueError('Product and category cannot be blank')
                qty = int(row['quantity'].strip())
                price = Decimal(row['unit_price'].strip())
                cost = Decimal(row['unit_cost'].strip())
                status = row['status'].strip().title()
                if not price.is_finite() or not cost.is_finite():
                    raise ValueError('Price and cost must be finite numbers')
                if qty <= 0 or price < 0 or cost < 0:
                    raise ValueError('Quantity must be positive; price and cost nonnegative')
                if price != cash(price) or cost != cash(cost):
                    raise ValueError('Prices and costs must have at most two decimal places (CAD cents)')
                if status not in STATUSES:
                    raise ValueError('Status must be Completed, Refunded or Cancelled')
                revenue = cash(price * qty) if status == 'Completed' else Decimal('0.00')
                cogs = cash(cost * qty) if status == 'Completed' else Decimal('0.00')
                accepted.append(dict(order_id=oid, date=when.isoformat(), month=when.strftime('%Y-%m'),
                                     product=product, category=category, quantity=qty,
                                     unit_price=cash(price), unit_cost=cash(cost), status=status,
                                     revenue=revenue, cogs=cogs, gross_profit=cash(revenue-cogs)))
                seen.add(oid)
            except (ValueError, InvalidOperation, TypeError, AttributeError, OverflowError) as exc:
                errors.append((line, str(exc)))
    if not accepted:
        raise ValueError('No valid orders found. See the input format in README.md.')

    m = defaultdict(lambda: dict(orders=0, completed=0, refunded=0, cancelled=0,
                                 revenue=Decimal(0), profit=Decimal(0)))
    p = defaultdict(lambda: dict(units=0, revenue=Decimal(0), profit=Decimal(0)))
    for order in accepted:
        mon = m[order['month']]
        mon['orders'] += 1
        mon[order['status'].lower()] += 1
        mon['revenue'] += order['revenue']
        mon['profit'] += order['gross_profit']
        if order['status'] == 'Completed':
            prod = p[(order['product'], order['category'])]
            prod['units'] += order['quantity']
            prod['revenue'] += order['revenue']
            prod['profit'] += order['gross_profit']
    months = sorted(m.items())
    products = sorted(p.items(), key=lambda item: (-item[1]['revenue'], item[0][0], item[0][1]))
    csv_fields = FIELDS + ['month', 'revenue', 'cogs', 'gross_profit']
    write_csv(out_dir/'clean_orders.csv', csv_fields,
              ([o[k] for k in csv_fields] for o in accepted),
              text_columns=('order_id','date','product','category','status','month'))
    write_csv(out_dir/'monthly_summary.csv',
              ['month', 'orders', 'completed', 'refunded', 'cancelled', 'revenue_cad', 'gross_profit_cad', 'gross_margin_percent'],
              ([key, v['orders'], v['completed'], v['refunded'], v['cancelled'], cash(v['revenue']), cash(v['profit']),
                cash(v['profit']/v['revenue']*100) if v['revenue'] else Decimal(0)] for key,v in months),
              text_columns=('month',))
    write_csv(out_dir/'product_summary.csv',
              ['product','category','completed_units','revenue_cad','gross_profit_cad'],
              ([name, category, v['units'], cash(v['revenue']), cash(v['profit'])] for (name, category),v in products),
              text_columns=('product','category'))
    sales = cash(sum((o['revenue'] for o in accepted), Decimal(0)))
    profit = cash(sum((o['gross_profit'] for o in accepted), Decimal(0)))
    count = lambda status: sum(o['status'] == status for o in accepted)
    stats = dict(valid=len(accepted), rejected=len(errors), completed=count('Completed'), refunded=count('Refunded'),
                 cancelled=count('Cancelled'), revenue=sales, gross_profit=profit, source_name=input_path.name,
                 months=months, products=products)
    summary = [
        'SALES AUTOMATION | VALIDATION REPORT',
        'Source: ' + input_path.name,
        'Data: ' + ('fictional demo data' if demo else 'user-provided local CSV'),
        f'Valid rows: {stats["valid"]}', f'Rejected rows: {stats["rejected"]}',
        f'Completed orders: {stats["completed"]}', f'Refunded orders: {stats["refunded"]}',
        f'Cancelled orders: {stats["cancelled"]}',
        f'Completed-order sales CAD: {sales}', f'Gross profit CAD: {profit}',
        'Revenue and COGS count completed orders only. Fully refunded and cancelled orders have zero recognized revenue and COGS.',
        'Gross profit excludes tax, fees, shipping and overhead. Partial refunds not supported.',
    ]
    if errors:
        summary += ['', 'REJECTED ROWS'] + [f'Line {line}: {reason}' for line, reason in errors]
    (out_dir/'quality_report.txt').write_text('\n'.join(summary)+'\n', encoding='utf-8')
    (out_dir/'dashboard.html').write_text(html_dashboard(stats, demo=demo), encoding='utf-8')
    (out_dir/'report_metadata.json').write_text(json.dumps({
        'source': input_path.name, 'demo': demo, 'accepted': stats['valid'],
        'rejected': stats['rejected'], 'completed': stats['completed'],
        'refunded': stats['refunded'], 'cancelled': stats['cancelled'],
        'revenue_cad': str(sales), 'gross_profit_cad': str(profit),
    }, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('\n'.join(summary[:10]))
    print('\nDashboard: ' + str((out_dir/'dashboard.html').resolve()))
    return stats


def main():
    parser = argparse.ArgumentParser(description='Generate an offline CSV and HTML sales dashboard.')
    parser.add_argument('csv_file', nargs='?', default='sample_orders.csv', help='Input CSV')
    parser.add_argument('--out', default='my_report', help='Output directory')
    parser.add_argument('--demo', action='store_true', help='Mark result as fictional portfolio demonstration')
    args = parser.parse_args()
    try:
        build(args.csv_file, args.out, demo=args.demo)
    except (OSError, ValueError, csv.Error) as exc:
        parser.exit(1, f'ERROR: {exc}\n')


if __name__ == '__main__':
    main()
