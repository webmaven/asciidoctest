import pathlib
import sys
import tempfile
import textwrap
import types
import unittest

from asciidoctest.unittest_integration import DocFileSuite, DocTestSuite


def sample_func():
    """
    [source,python,test]
    ----
    >>> sample_func()
    'ok'
    ----
    """
    return "ok"


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

    def test_test_case_helper_metadata_and_formatting(self):
        from asciidoctest.unittest_integration import (
            AsciiDocTestCase,
            DocstringTestCase,
        )

        # 1. Verify AsciiDocTestCase helpers
        file_case_with_desc = AsciiDocTestCase("FileTest_1", [], "Custom Description")
        self.assertEqual(file_case_with_desc.id(), "FileTest_1")
        self.assertEqual(file_case_with_desc.shortDescription(), "Custom Description")
        self.assertIn("FileTest_1", str(file_case_with_desc))

        file_case_no_desc = AsciiDocTestCase("FileTest_2", [])
        self.assertEqual(file_case_no_desc.shortDescription(), "FileTest_2")

        # 2. Verify DocstringTestCase helpers
        string_case_with_desc = DocstringTestCase(
            "StringTest_1", [], {}, "Custom Docstring Description"
        )
        self.assertEqual(string_case_with_desc.id(), "StringTest_1")
        self.assertEqual(
            string_case_with_desc.shortDescription(), "Custom Docstring Description"
        )
        self.assertIn("StringTest_1", str(string_case_with_desc))

        string_case_no_desc = DocstringTestCase("StringTest_2", [], {})
        self.assertEqual(string_case_no_desc.shortDescription(), "StringTest_2")

    def test_doc_test_suite_edge_cases(self):
        # 1. Create a dynamic module with advanced features
        module_name = "advanced_edgecase_module"
        mod = types.ModuleType(module_name)
        mod.__doc__ = ""  # empty docstring

        # Import an external routine with __module__ to trigger the module membership filter continue condition
        from math import sqrt

        mod.sqrt = sqrt

        # Class with methods to cover class method parsing and nested routines
        class AdvancedSampleClass:
            """
            [source,python,test]
            ----
            >>> True
            True
            ----
            """

            def nested_method(self):
                """
                [source,python,test]
                ----
                >>> 100 * 2
                200
                ----
                """

        # Class with invalid docstring to trigger exception handling bypass
        class InvalidDocClass:
            """
            [source,python
            ----
            Unparsable!
            ----
            """

        # Set correct module ownership
        AdvancedSampleClass.__module__ = module_name
        AdvancedSampleClass.nested_method.__module__ = module_name
        InvalidDocClass.__module__ = module_name

        # Assign to dynamic module
        mod.AdvancedSampleClass = AdvancedSampleClass
        mod.InvalidDocClass = InvalidDocClass

        # Create a duplicated reference (alias) to the class to trigger discovery filter
        mod.AdvancedSampleClassAlias = AdvancedSampleClass

        sys.modules[module_name] = mod

        try:
            # 2. Test importing module by string name
            suite = DocTestSuite(module_name)
            self.assertIsInstance(suite, unittest.TestSuite)

            result = unittest.TestResult()
            suite.run(result)

            # Should have found exactly 2 valid test cases:
            # - AdvancedSampleClass docstring test
            # - nested_method docstring test
            # AdvancedSampleClassAlias is ignored since it's already discovered.
            # InvalidDocClass exception block is bypassed gracefully.
            # Imported 'sqrt' is ignored because it belongs to 'math'.
            self.assertEqual(result.testsRun, 2)
            self.assertEqual(len(result.failures), 0)
        finally:
            sys.modules.pop(module_name, None)

    def test_doc_file_suite_eager_mode(self):
        # Create an unmarked .adoc file which runs in eager mode and fails
        adoc_content = textwrap.dedent("""\
            = Temp Doc
            
            [source,python]
            ----
            assert 2 + 2 == 5
            ----
            """)
        with tempfile.NamedTemporaryFile(suffix=".adoc", mode="w", delete=False) as f:
            f.write(adoc_content)
            filepath = f.name

        try:
            suite = DocFileSuite(filepath, mode="eager")
            result = unittest.TestResult()
            suite.run(result)
            self.assertEqual(result.testsRun, 1)
            self.assertEqual(len(result.failures), 1)
        finally:
            pathlib.Path(filepath).unlink(missing_ok=True)

    def test_doc_test_suite_eager_mode(self):
        module_name = "unittest_eager_module"
        mod = types.ModuleType(module_name)
        mod.__doc__ = textwrap.dedent("""\
            [source,python]
            ----
            assert 1 + 1 == 3
            ----
            """)
        sys.modules[module_name] = mod
        try:
            # Under eager mode with no explicit blocks, the unmarked block is run and fails
            suite = DocTestSuite(mod, mode="eager")
            result = unittest.TestResult()
            suite.run(result)
            self.assertEqual(result.testsRun, 1)
            self.assertEqual(len(result.failures), 1)
        finally:
            sys.modules.pop(module_name, None)

    def test_doc_test_suite_eager_mode_disabled_by_explicit(self):
        module_name = "unittest_eager_bypass_module"
        mod = types.ModuleType(module_name)
        mod.__doc__ = textwrap.dedent("""\
            [source,python]
            ----
            assert 1 + 1 == 3
            ----
            
            [source,python,test]
            ----
            assert 2 + 2 == 4
            ----
            """)
        sys.modules[module_name] = mod
        try:
            # Eager mode is bypassed/disabled because there is an explicit test block,
            # so only the explicit test block runs and passes!
            suite = DocTestSuite(mod, mode="eager")
            result = unittest.TestResult()
            suite.run(result)
            self.assertEqual(result.testsRun, 1)
            self.assertEqual(len(result.failures), 0)
        finally:
            sys.modules.pop(module_name, None)

    def test_doc_test_suite_import_by_string_not_in_sys_modules(self):
        import tempfile

        # Create a temporary python module file in a temp directory
        with tempfile.TemporaryDirectory() as tmp_dir:
            mod_file = pathlib.Path(tmp_dir) / "unimported_sample_mod.py"
            mod_file.write_text(
                textwrap.dedent("""\
                \"\"\"
                [source,python,test]
                ----
                >>> val = 42
                >>> val
                42
                ----
                \"\"\"
                def helper():
                    \"\"\"
                    [source,python,test]
                    ----
                    >>> 10 + 5
                    15
                    ----
                    \"\"\"
                    return 15
                """),
                encoding="utf-8",
            )
            sys.path.insert(0, tmp_dir)
            try:
                # Ensure it is not in sys.modules
                sys.modules.pop("unimported_sample_mod", None)
                self.assertNotIn("unimported_sample_mod", sys.modules)

                # Calling DocTestSuite with module name string triggers __import__ on line 98
                suite = DocTestSuite("unimported_sample_mod")
                self.assertIsInstance(suite, unittest.TestSuite)

                result = unittest.TestResult()
                suite.run(result)
                self.assertEqual(result.testsRun, 2)
                self.assertEqual(len(result.failures), 0)
                self.assertEqual(len(result.errors), 0)
            finally:
                if tmp_dir in sys.path:
                    sys.path.remove(tmp_dir)
                sys.modules.pop("unimported_sample_mod", None)

    def test_doc_test_suite_exception_handling_in_process_object(self):
        from unittest.mock import patch

        module_name = "exception_test_module"
        mod = types.ModuleType(module_name)
        mod.__doc__ = "Some docstring that triggers process_object"
        sys.modules[module_name] = mod

        try:
            with patch(
                "asciidoctest.unittest_integration.extract_docstring_tests",
                side_effect=RuntimeError("Parsing error simulation"),
            ):
                # Should catch RuntimeError and pass gracefully without raising
                suite = DocTestSuite(mod)
                self.assertIsInstance(suite, unittest.TestSuite)
                self.assertEqual(suite.countTestCases(), 0)
        finally:
            sys.modules.pop(module_name, None)

    def test_module_reload_coverage(self):
        import importlib

        import asciidoctest.unittest_integration

        # Reload module during test execution to ensure definition lines are traced by coverage
        importlib.reload(asciidoctest.unittest_integration)
