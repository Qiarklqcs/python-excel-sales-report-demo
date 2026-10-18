import csv
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from analyze_orders import build

ROOT = Path(__file__).resolve().parents[1]
HEADERS = ['order_id', 'date', 'product', 'category', 'quantity', 'unit_price', 'unit_cost', 'status']


def order(id, **kwargs):
    return {**dict(order_id=id, date='2026-10-02', product='Desk light', category='Office', quantity='2',
                   unit_price='10', unit_cost='3', status='Completed'), **kwargs}


def write(path, orders):
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, HEADERS)
        w.writeheader()
        w.writerows(orders)


class ReportTests(unittest.TestCase):
    def test_full_demonstration(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)/'out'
            r = build(ROOT/'sample_orders.csv', out, demo=True)
            self.assertEqual((r['valid'],r['rejected'],r['completed'],r['refunded'],r['cancelled']), (132,0,114,10,8))
            self.assertEqual((r['revenue'],r['gross_profit']), (Decimal('6674.00'),Decimal('3909.30')))
            for filename in ['dashboard.html','monthly_summary.csv','product_summary.csv','clean_orders.csv',
                             'quality_report.txt','report_metadata.json']:
                self.assertTrue((out/filename).is_file(), filename)
            page=(out/'dashboard.html').read_text(encoding='utf-8')
            self.assertIn('$6,674.00',page)
            self.assertIn('DEMO · FICTIONAL ORDERS',page)
            self.assertEqual(json.loads((out/'report_metadata.json').read_text())['completed'],114)

    def test_refresh_data_changes_all_reports(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d); path=base/'source.csv'; dest=base/'report'
            write(path,[order('001'),order('002',status='Refunded'),order('003',status='Cancelled')])
            first=build(path,dest)
            self.assertEqual((first['revenue'],first['gross_profit']), (Decimal('20.00'),Decimal('14.00')))
            self.assertIn('$20.00',(dest/'dashboard.html').read_text())
            write(path,[order('001',unit_price='22',unit_cost='4'),order('002',status='Refunded')])
            second=build(path,dest)
            self.assertEqual((second['revenue'],second['gross_profit']), (Decimal('44.00'),Decimal('36.00')))
            self.assertIn('$44.00',(dest/'dashboard.html').read_text())
            self.assertNotIn('$20.00',(dest/'dashboard.html').read_text())
            with (dest/'monthly_summary.csv').open(encoding='utf-8-sig') as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(rows[0]['revenue_cad'],'44.00')

    def test_bad_rows_script_text_and_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d); source=base/'orders.csv'; target=base/'out'
            write(source,[order('A1'),order('A1'),order('A2',date='2026-13-01'),order('A3',quantity='-3'),
                          order('A4',unit_price='NaN'),order('A5',status='Unknown'),
                          order('A6',product='<script>alert(1)</script>'),
                          order('A7',product='=HYPERLINK("http://invalid.example")')])
            result=build(source,target)
            self.assertEqual((result['valid'],result['rejected']),(3,5))
            csv_text=(target/'clean_orders.csv').read_text(encoding='utf-8-sig')
            self.assertIn("'=HYPERLINK",csv_text)
            page=(target/'dashboard.html').read_text()
            self.assertIn('&lt;script&gt;',page)
            self.assertNotIn('<script>alert(1)</script>',page)

    def test_all_invalid_rows(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d); path=base/'bad.csv'
            write(path,[order('X',quantity='0')])
            with self.assertRaisesRegex(ValueError,'No valid orders'):
                build(path,base/'output')


    def test_fractional_cents_rejected_and_negative_profit_is_numeric(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d); path=base/'input.csv'; dest=base/'results'
            write(path,[order('001',unit_price='3.00',unit_cost='5.00'),
                        order('002',unit_price='2.005',unit_cost='1.00')])
            r=build(path,dest)
            self.assertEqual((r['valid'],r['rejected']),(1,1))
            self.assertEqual(r['gross_profit'],Decimal('-4.00'))
            with (dest/'monthly_summary.csv').open(encoding='utf-8-sig',newline='') as f:
                row=next(csv.DictReader(f))
            self.assertEqual(row['gross_profit_cad'],'-4.00')
            self.assertNotIn("'-4.00",(dest/'monthly_summary.csv').read_text(encoding='utf-8-sig'))

if __name__=='__main__': unittest.main()
