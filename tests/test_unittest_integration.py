import unittest
import tempfile
import pathlib
import sys
import types
import textwrap
from asciidoctest.unittest_integration import DocFileSuite, DocTestSuite

def sample_func():
    """
    [source,python,test]
    ----
    >>> sample_func()
    'ok'
    ----
    """
    return 'ok'

class TestUnittestIntegration(unittest.TestCase):
    def test_doc_file_suite_success(self):
        # Create a temporary .adoc file with passing test
        adoc_content = textwrap.dedent("""\
            = Temp Doc
            
            [source,python,test]
            ----
            a = 1
            assert a == 1
            ----
            """)
        with tempfile.NamedTemporaryFile(suffix=".adoc", mode="w", delete=False) as f:
            f.write(adoc_content)
            filepath = f.name
            
        try:
            suite = DocFileSuite(filepath)
            self.assertIsInstance(suite, unittest.TestSuite)
            
            # Run the suite
            result = unittest.TestResult()
            suite.run(result)
            self.assertEqual(result.testsRun, 1)
            self.assertEqual(len(result.failures), 0)
            self.assertEqual(len(result.errors), 0)
        finally:
            pathlib.Path(filepath).unlink(missing_ok=True)


    def test_doc_file_suite_failure(self):
        # Create a temporary .adoc file with failing test
        adoc_content = textwrap.dedent("""\
            = Temp Doc
            
            [source,python,test]
            ----
            assert 1 == 2
            ----
            """)
        with tempfile.NamedTemporaryFile(suffix=".adoc", mode="w", delete=False) as f:
            f.write(adoc_content)
            filepath = f.name
            
        try:
            suite = DocFileSuite(filepath)
            result = unittest.TestResult()
            suite.run(result)
            self.assertEqual(result.testsRun, 1)
            self.assertEqual(len(result.failures), 1)
        finally:
            pathlib.Path(filepath).unlink(missing_ok=True)


    def test_doc_test_suite_success(self):
        # Dynamically create a module with passing docstring tests
        module_name = "dynamic_test_module"
        mod = types.ModuleType(module_name)
        mod.__doc__ = textwrap.dedent("""\
            = My Module
            
            [source,python,test]
            ----
            >>> 1 + 1
            2
            ----
            """)
        # Assign sample_func to dynamic module, setting its __module__
        # to match mod.__name__ so DocTestSuite's module-filter accepts it.
        sample_func.__module__ = module_name
        mod.sample_func = sample_func
        sys.modules[module_name] = mod
        
        try:
            suite = DocTestSuite(mod)
            self.assertIsInstance(suite, unittest.TestSuite)
            
            result = unittest.TestResult()
            suite.run(result)
            # Should have found 2 docstrings with tests: module-level and sample_func-level
            self.assertEqual(result.testsRun, 2)
            self.assertEqual(len(result.failures), 0)
            self.assertEqual(len(result.errors), 0)
        finally:
            sys.modules.pop(module_name, None)
            # Restore original __module__ to avoid breaking subsequent runs or collections
            sample_func.__module__ = "tests.test_unittest_integration"
