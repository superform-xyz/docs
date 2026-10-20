"""Public regression tests; no private checkout, Go, or network required."""
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('validate_operate.py')
ROOT = SCRIPT.parent.parent


class OperateValidationTests(unittest.TestCase):
    def load(self):
        self.assertTrue(SCRIPT.is_file(), 'portable final-MDX runner must ship in this repository')
        spec = importlib.util.spec_from_file_location('validate_operate', SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_extracts_final_docs_and_minimum_public_capture(self):
        runner = self.load()
        fixture, manifest, pages = runner.extract_docs(ROOT)
        self.assertEqual(len(fixture['snippets']), 22)
        self.assertEqual(len(fixture['cases']), 67)
        self.assertEqual(len(fixture['live']), 4)
        self.assertEqual(len(manifest), 17)
        with contextlib.redirect_stdout(io.StringIO()):
            runner.test_python_snippets(pages)

    def test_monitoring_negative_mutation_is_detected(self):
        runner = self.load()
        _, _, pages = runner.extract_docs(ROOT)
        route = 'automation/monitoring'
        pages[route] = [(lang, body.replace('return "UNKNOWN"', 'return "HEALTHY"'))
                        for lang, body in pages[route]]
        with self.assertRaises(AssertionError):
            runner.test_python_snippets(pages)

    def test_poller_wall_clock_checkpoint_regression_is_detected(self):
        runner = self.load()
        _, _, pages = runner.extract_docs(ROOT)
        route = 'automation/webhooks'
        pages[route] = [(lang, body.replace('return ordered, high', 'return ordered, end_time'))
                        for lang, body in pages[route]]
        with self.assertRaises(AssertionError):
            runner.test_python_snippets(pages)

    def copy_docs(self, target):
        for source in [ROOT / 'operate.mdx', *(ROOT / 'operate').rglob('*.mdx')]:
            path = target / source.relative_to(ROOT)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source.read_text())

    def test_inventory_covers_every_page_and_rejects_new_fences(self):
        runner = self.load()
        with tempfile.TemporaryDirectory() as temp:
            docs = Path(temp)
            self.copy_docs(docs)
            inventory = runner.inventory_docs(docs)
            self.assertEqual(len(inventory), 39)
            page = docs / 'operate/ui/home.mdx'
            for opening, closing in [('```python', '```'), ('  ~~~~python', '  ~~~~')]:
                original = page.read_text()
                page.write_text(original + f'\n{opening}\nprint("unreviewed")\n{closing}\n')
                with self.assertRaisesRegex(AssertionError, 'inventory'):
                    runner.inventory_docs(docs)
                page.write_text(original)

    def test_capture_rejects_repeated_identifier_and_threshold_drift(self):
        runner = self.load()
        for route, old, new in [
            ('strategy/variables', '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913', '0x833589fcd6edb6e08f4c7c32d4f71b54bda02914'),
            ('playbooks/carry', '52% <= LTV < 55%', '53% <= LTV < 55%'),
            ('playbooks/carry', '6 / RUNNING', '7 / RUNNING'),
            ('playbooks/deleverage', 'LTV >= 55%', 'LTV >= 56%'),
            ('ui/intent-history', 'istr=a8d25935-9f6d-4046-a87a-82048af0cc1c', 'istr=5db21999-c05c-4af3-8824-9f7ecc746576'),
            ('strategy/variables', '`token_0x833589fcd6edb6e08f4c7c32d4f71b54bda02913_amount`', '`token_0xc441a2cc3a528b6312740448a70cc4d40f4d7bfc_amount`'),
        ]:
            with self.subTest(route=route, old=old), tempfile.TemporaryDirectory() as temp:
                docs = Path(temp)
                self.copy_docs(docs)
                page = docs / 'operate' / (route + '.mdx')
                self.assertIn(old, page.read_text())
                page.write_text(page.read_text().replace(old, new))
                with self.assertRaisesRegex(AssertionError, 'capture consistency'):
                    runner.validate_capture_consistency(docs)

    def test_modified_plan_is_rejected_against_capture(self):
        runner = self.load()
        with tempfile.TemporaryDirectory() as temp:
            docs = Path(temp)
            for route in runner.OWNED:
                name = Path('operate') / (route + '.mdx')
                target = docs / name
                target.parent.mkdir(parents=True, exist_ok=True)
                text = (ROOT / name).read_text()
                if route == 'strategy/action-config':
                    self.assertIn('"use_prev_hook_amount": true', text)
                    text = text.replace('"use_prev_hook_amount": true', '"use_prev_hook_amount": false')
                target.write_text(text)
            with self.assertRaisesRegex(AssertionError, 'differs from capture'):
                runner.extract_docs(docs)


if __name__ == '__main__':
    unittest.main()
