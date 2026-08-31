import pathlib
import textwrap
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from _pytest._code.code import ExceptionInfo

from asciidoctest.pytest_plugin import (
    AsciiDocFile,
    AsciiDocItem,
    DocstringTestItem,
    PythonDocstringFile,
    pytest_addoption,
    pytest_collect_file,
)
from asciidoctest.runner import AsciiDocTestFailure


class MockBlock:
    """Mock test block matching asciidoctest runner requirements."""

    def __init__(
        self,
        content: str,
        is_interactive: bool = False,
        line_number: int = 1,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        self.content = content
        self.is_interactive = is_interactive
        self.line_number = line_number
        self.attributes = attributes if attributes is not None else {"test": True}


# ============================================================================
# pytest_addoption Tests
# ============================================================================


def test_pytest_addoption_with_real_parser() -> None:
    """Test pytest_addoption adds expected CLI options and ini entries."""
    parser = pytest.Parser(_ispytest=True)
    pytest_addoption(parser)

    # The option is added to the named "asciidoctest" group, not _anonymous.
    # Collect options from all groups to find --asciidoctest-mode.
    all_option_names: list[tuple[str, ...]] = []
    for group in parser._groups:
        all_option_names.extend(opt.names() for opt in group.options)
    all_option_names.extend(opt.names() for opt in parser._anonymous.options)
    assert any("--asciidoctest-mode" in names for names in all_option_names)

    # Verify ini option is registered with default 'explicit'
    # _inidict stores (help, type, default) tuples
    assert "asciidoctest_mode" in parser._inidict
    assert parser._inidict["asciidoctest_mode"][2] == "explicit"


def test_pytest_addoption_with_dummy_parser() -> None:
    """Test pytest_addoption interactions with a mocked parser."""
    dummy_parser = MagicMock()
    dummy_group = MagicMock()
    dummy_parser.getgroup.return_value = dummy_group

    pytest_addoption(dummy_parser)

    dummy_parser.getgroup.assert_called_once_with("asciidoctest")
    dummy_group.addoption.assert_called_once_with(
        "--asciidoctest-mode",
        action="store",
        default="explicit",
        choices=["explicit", "eager"],
        help="asciidoctest target selection mode: 'explicit' or 'eager'",
    )
    dummy_parser.addini.assert_called_once_with(
        "asciidoctest_mode",
        default="explicit",
        help="asciidoctest target selection mode: 'explicit' or 'eager'",
    )


# ============================================================================
# pytest_collect_file Tests
# ============================================================================


def test_pytest_collect_file_non_matching_extensions(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """pytest_collect_file returns None for non-matching extensions."""
    session = request.session
    for ext in [".txt", ".md", ".rst", ".json", ".yaml", ".c", ".h"]:
        file_path = tmp_path / f"test{ext}"
        file_path.write_text("dummy content", encoding="utf-8")
        assert pytest_collect_file(file_path, session) is None


def test_pytest_collect_file_adoc_file(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """pytest_collect_file returns AsciiDocFile for .adoc files."""
    session = request.session
    file_path = tmp_path / "guide.adoc"
    file_path.write_text("= Title\n\nSome text", encoding="utf-8")

    collector = pytest_collect_file(file_path, session)
    assert isinstance(collector, AsciiDocFile)
    assert collector.path == file_path


def test_pytest_collect_file_py_without_markers(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """pytest_collect_file returns None for .py files without docstring doctest markers."""
    session = request.session

    # 1. Plain code
    plain_py = tmp_path / "plain.py"
    plain_py.write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    assert pytest_collect_file(plain_py, session) is None

    # 2. Empty file
    empty_py = tmp_path / "empty.py"
    empty_py.write_text("", encoding="utf-8")
    assert pytest_collect_file(empty_py, session) is None

    # 3. Docstring without [source,python
    docstring_py = tmp_path / "standard_doc.py"
    docstring_py.write_text(
        'def add(a, b):\n    """Sum numbers."""\n    return a + b\n',
        encoding="utf-8",
    )
    assert pytest_collect_file(docstring_py, session) is None


def test_pytest_collect_file_py_with_markers(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """pytest_collect_file returns PythonDocstringFile for .py files with markers."""
    session = request.session

    # Exact match [source,python
    py1 = tmp_path / "exact.py"
    py1.write_text(
        '"""\n[source,python,test]\n----\n>>> 1\n1\n----\n"""\n', encoding="utf-8"
    )
    collector1 = pytest_collect_file(py1, session)
    assert isinstance(collector1, PythonDocstringFile)
    assert collector1.path == py1

    # Whitespace match [source , python
    py2 = tmp_path / "spaced.py"
    py2.write_text(
        '"""\n[source , python , test]\n----\n>>> 2\n2\n----\n"""\n', encoding="utf-8"
    )
    collector2 = pytest_collect_file(py2, session)
    assert isinstance(collector2, PythonDocstringFile)
    assert collector2.path == py2


def test_pytest_collect_file_unreadable_file(request: pytest.FixtureRequest) -> None:
    """pytest_collect_file catches file reading exceptions and returns None."""
    session = request.session
    non_existent = pathlib.Path("/nonexistent/path/to/missing.py")
    assert pytest_collect_file(non_existent, session) is None


# ============================================================================
# AsciiDocFile.collect Tests
# ============================================================================


def _create_mock_config(
    option_mode: str | None = None, ini_mode: str | None = None
) -> MagicMock:
    """Create a mock pytest config with getoption and getini."""
    config = MagicMock()
    config.getoption.return_value = option_mode
    config.getini.return_value = ini_mode
    return config


def test_asciidoc_file_collect_explicit_mode(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """AsciiDocFile.collect under explicit mode collects marked blocks and skips unmarked."""
    adoc = tmp_path / "explicit.adoc"
    adoc.write_text(
        textwrap.dedent("""\
        = Document
        
        [source,python]
        ----
        x = 100
        ----
        
        [source,python,test]
        ----
        y = 200
        assert y == 200
        ----
        """),
        encoding="utf-8",
    )

    collector = AsciiDocFile.from_parent(request.session, path=adoc)
    # Configure explicit mode
    collector.config = _create_mock_config(option_mode="explicit")

    items = list(collector.collect())
    assert len(items) == 1
    assert isinstance(items[0], AsciiDocItem)
    assert items[0].name == "asciidoctest"
    assert len(items[0].blocks) == 1
    assert "y = 200" in items[0].blocks[0].content


def test_asciidoc_file_collect_eager_mode(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """AsciiDocFile.collect under eager mode collects unmarked blocks."""
    adoc = tmp_path / "eager.adoc"
    adoc.write_text(
        textwrap.dedent("""\
        = Document
        
        [source,python]
        ----
        x = 100
        assert x == 100
        ----
        """),
        encoding="utf-8",
    )

    collector = AsciiDocFile.from_parent(request.session, path=adoc)
    # Configure eager mode
    collector.config = _create_mock_config(option_mode="eager")

    items = list(collector.collect())
    assert len(items) == 1
    assert isinstance(items[0], AsciiDocItem)
    assert len(items[0].blocks) == 1


def test_asciidoc_file_collect_mode_fallback(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """AsciiDocFile.collect falls back to ini or default 'explicit'."""
    adoc = tmp_path / "mode_test.adoc"
    adoc.write_text(
        textwrap.dedent("""\
        [source,python]
        ----
        x = 1
        ----
        """),
        encoding="utf-8",
    )

    # 1. Fallback to ini 'eager'
    collector1 = AsciiDocFile.from_parent(request.session, path=adoc)
    collector1.config = _create_mock_config(option_mode=None, ini_mode="eager")
    items1 = list(collector1.collect())
    assert len(items1) == 1

    # 2. Fallback to default 'explicit' when both option and ini are None
    collector2 = AsciiDocFile.from_parent(request.session, path=adoc)
    collector2.config = _create_mock_config(option_mode=None, ini_mode=None)
    items2 = list(collector2.collect())
    assert len(items2) == 0


def test_asciidoc_file_collect_empty_blocks(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """AsciiDocFile.collect yields nothing when no matching test blocks exist."""
    adoc = tmp_path / "empty.adoc"
    adoc.write_text("= Title\n\nNo code blocks here.\n", encoding="utf-8")

    collector = AsciiDocFile.from_parent(request.session, path=adoc)
    collector.config = _create_mock_config(option_mode="explicit")

    items = list(collector.collect())
    assert items == []


def test_asciidoc_file_collect_parse_failure(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """AsciiDocFile.collect raises ValueError when parse_adoc_tests fails."""
    adoc = tmp_path / "bad.adoc"
    adoc.write_text("some content", encoding="utf-8")

    collector = AsciiDocFile.from_parent(request.session, path=adoc)
    collector.config = _create_mock_config()

    with patch(
        "asciidoctest.pytest_plugin.parse_adoc_tests",
        side_effect=RuntimeError("Corrupt structure"),
    ):
        with pytest.raises(
            ValueError, match="Failed to parse AsciiDoc file.*Corrupt structure"
        ):
            list(collector.collect())


# ============================================================================
# AsciiDocItem Tests
# ============================================================================


def test_asciidoc_item_init_and_fixtureinfo(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """AsciiDocItem correctly sets _fixtureinfo when session has fixturemanager."""
    adoc = tmp_path / "doc.adoc"
    adoc.write_text("= Doc\n", encoding="utf-8")
    parent_file = AsciiDocFile.from_parent(request.session, path=adoc)

    block = MockBlock(
        content="assert True\n",
        line_number=1,
        attributes={"test": True},
    )
    item = AsciiDocItem.from_parent(parent_file, name="asciidoctest", blocks=[block])
    assert item._fixtureinfo is not None

    # Test the no-_fixturemanager branch by temporarily removing the attribute
    session = request.session
    original_fm = session._fixturemanager
    try:
        # delattr triggers getattr returning None in __init__
        del session._fixturemanager
        item_no_fm = AsciiDocItem.from_parent(
            parent_file, name="asciidoctest_no_fm", blocks=[block]
        )
        assert item_no_fm._fixtureinfo is None
    finally:
        session._fixturemanager = original_fm


def test_asciidoc_item_runtest_success(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """AsciiDocItem.runtest executes sequential blocks in shared globals."""
    adoc = tmp_path / "test.adoc"
    adoc.write_text("= Doc\n", encoding="utf-8")
    parent_file = AsciiDocFile.from_parent(request.session, path=adoc)

    block1 = MockBlock(
        content="val = 42\nassert val == 42\n",
        line_number=1,
        attributes={"test": True},
    )

    item = AsciiDocItem.from_parent(parent_file, name="asciidoctest", blocks=[block1])
    # Should run without error
    item.runtest()


def test_asciidoc_item_runtest_failure(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """AsciiDocItem.runtest raises AsciiDocTestFailure on mismatch or assertion error."""
    adoc = tmp_path / "fail.adoc"
    adoc.write_text("= Doc\n", encoding="utf-8")
    parent_file = AsciiDocFile.from_parent(request.session, path=adoc)

    block = MockBlock(
        content="assert 1 == 2\n",
        line_number=3,
        attributes={"test": True},
    )
    item = AsciiDocItem.from_parent(parent_file, name="asciidoctest", blocks=[block])

    with pytest.raises(AsciiDocTestFailure):
        item.runtest()


def test_asciidoc_item_repr_failure(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """AsciiDocItem.repr_failure formats AsciiDocTestFailure as string and falls back for others."""
    adoc = tmp_path / "test.adoc"
    adoc.write_text("= Doc\n", encoding="utf-8")
    parent_file = AsciiDocFile.from_parent(request.session, path=adoc)
    item = AsciiDocItem.from_parent(parent_file, name="asciidoctest", blocks=[])

    # 1. With AsciiDocTestFailure
    try:
        raise AsciiDocTestFailure("Test failed at line 5: assertion failed")
    except AsciiDocTestFailure:
        excinfo1 = ExceptionInfo.from_current()

    repr1 = item.repr_failure(excinfo1)
    assert isinstance(repr1, str)
    assert "Test failed at line 5" in repr1

    # 2. With generic RuntimeError
    try:
        raise RuntimeError("Generic unexpected failure")
    except RuntimeError:
        excinfo2 = ExceptionInfo.from_current()

    repr2 = item.repr_failure(excinfo2)
    assert "Generic unexpected failure" in str(repr2)


def test_asciidoc_item_reportinfo(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """AsciiDocItem.reportinfo returns path, lineno=0, and formatted name."""
    adoc = tmp_path / "sample.adoc"
    adoc.write_text("= Doc\n", encoding="utf-8")
    parent_file = AsciiDocFile.from_parent(request.session, path=adoc)
    item = AsciiDocItem.from_parent(parent_file, name="asciidoctest", blocks=[])

    path, lineno, name = item.reportinfo()
    assert path == adoc
    assert lineno == 0
    assert name == "AsciiDoc Document: asciidoctest"


# ============================================================================
# PythonDocstringFile.collect Tests
# ============================================================================


def test_python_docstring_file_collect_valid_docstrings(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """PythonDocstringFile.collect finds docstrings and yields DocstringTestItem."""
    py_file = tmp_path / "module.py"
    py_file.write_text(
        textwrap.dedent('''\
        def add(a, b):
            """
            [source,python,test]
            ----
            >>> add(1, 2)
            3
            ----
            """
            return a + b

        def sub(a, b):
            """
            [source,python,test]
            ----
            >>> sub(5, 3)
            2
            ----
            """
            return a - b
        '''),
        encoding="utf-8",
    )

    collector = PythonDocstringFile.from_parent(request.session, path=py_file)
    collector.config = _create_mock_config(option_mode="explicit")

    items = list(collector.collect())
    assert len(items) == 2
    assert isinstance(items[0], DocstringTestItem)
    assert items[0].name == "add_docstring"
    assert items[1].name == "sub_docstring"


def test_python_docstring_file_collect_empty_and_no_test_docstrings(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """PythonDocstringFile.collect yields nothing when docstrings have no tests."""
    py_file = tmp_path / "empty_docs.py"
    py_file.write_text(
        textwrap.dedent('''\
        def no_doc():
            pass

        def standard_doc():
            """Just standard text without any code blocks."""
            pass

        def unmarked_in_explicit():
            """
            [source,python]
            ----
            x = 10
            ----
            """
            pass
        '''),
        encoding="utf-8",
    )

    collector = PythonDocstringFile.from_parent(request.session, path=py_file)
    collector.config = _create_mock_config(option_mode="explicit")

    items = list(collector.collect())
    assert items == []


def test_python_docstring_file_collect_syntax_error(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """PythonDocstringFile.collect returns empty generator when syntax error occurs."""
    py_file = tmp_path / "invalid_syntax.py"
    py_file.write_text("def broken_syntax( : invalid", encoding="utf-8")

    collector = PythonDocstringFile.from_parent(request.session, path=py_file)
    collector.config = _create_mock_config()

    items = list(collector.collect())
    assert items == []


def test_python_docstring_file_collect_extract_docstring_exception(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """PythonDocstringFile.collect ignores individual docstring parsing exceptions."""
    py_file = tmp_path / "bad_doc.py"
    py_file.write_text(
        textwrap.dedent('''\
        def foo():
            """
            [source,python,test]
            ----
            >>> 1
            1
            ----
            """
            pass
        '''),
        encoding="utf-8",
    )

    collector = PythonDocstringFile.from_parent(request.session, path=py_file)
    collector.config = _create_mock_config()

    with patch(
        "asciidoctest.pytest_plugin.extract_docstring_tests",
        side_effect=ValueError("Docstring parse error"),
    ):
        items = list(collector.collect())
        assert items == []


def test_python_docstring_file_collect_mode_resolution(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """PythonDocstringFile.collect respects mode option and ini settings."""
    py_file = tmp_path / "mode_doc.py"
    py_file.write_text(
        textwrap.dedent('''\
        def compute():
            """
            [source,python]
            ----
            assert 10 == 10
            ----
            """
            pass
        '''),
        encoding="utf-8",
    )

    # 1. ini mode 'eager'
    collector1 = PythonDocstringFile.from_parent(request.session, path=py_file)
    collector1.config = _create_mock_config(option_mode=None, ini_mode="eager")
    items1 = list(collector1.collect())
    assert len(items1) == 1

    # 2. default 'explicit'
    collector2 = PythonDocstringFile.from_parent(request.session, path=py_file)
    collector2.config = _create_mock_config(option_mode=None, ini_mode=None)
    items2 = list(collector2.collect())
    assert len(items2) == 0


# ============================================================================
# DocstringTestItem Tests
# ============================================================================


def test_docstring_test_item_init_and_fixtureinfo(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """DocstringTestItem initializes lineno, blocks, and _fixtureinfo."""
    py_file = tmp_path / "mod.py"
    py_file.write_text("# empty\n", encoding="utf-8")
    parent_file = PythonDocstringFile.from_parent(request.session, path=py_file)

    block = MockBlock(
        content=">>> 1 + 1\n2\n",
        is_interactive=True,
        line_number=10,
        attributes={"test": True},
    )
    item = DocstringTestItem.from_parent(
        parent_file, name="myfunc_docstring", lineno=10, blocks=[block]
    )
    assert item.lineno == 10
    assert item.blocks == [block]
    assert item._fixtureinfo is not None

    # Test the no-_fixturemanager branch by temporarily removing the attribute
    session = request.session
    original_fm = session._fixturemanager
    try:
        del session._fixturemanager
        item_no_fm = DocstringTestItem.from_parent(
            parent_file, name="myfunc_docstring_no_fm", lineno=10, blocks=[block]
        )
        assert item_no_fm._fixtureinfo is None
    finally:
        session._fixturemanager = original_fm


def test_docstring_test_item_runtest_success(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """DocstringTestItem.runtest dynamically loads module and executes tests against it."""
    py_file = tmp_path / "sample_math.py"
    py_file.write_text(
        textwrap.dedent("""\
        def multiply(a, b):
            return a * b
        """),
        encoding="utf-8",
    )
    parent_file = PythonDocstringFile.from_parent(request.session, path=py_file)

    block = MockBlock(
        content=">>> multiply(3, 4)\n12\n",
        is_interactive=True,
        line_number=2,
        attributes={"test": True},
    )
    item = DocstringTestItem.from_parent(
        parent_file, name="multiply_docstring", lineno=2, blocks=[block]
    )

    # runtest should succeed and multiply should be accessible
    item.runtest()


def test_docstring_test_item_runtest_missing_loader_spec(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """DocstringTestItem.runtest raises ImportError if spec or spec.loader is None."""
    py_file = tmp_path / "missing_spec.py"
    py_file.write_text("x = 1\n", encoding="utf-8")
    parent_file = PythonDocstringFile.from_parent(request.session, path=py_file)

    item = DocstringTestItem.from_parent(
        parent_file, name="test_docstring", lineno=1, blocks=[]
    )

    # 1. spec is None
    with patch("importlib.util.spec_from_file_location", return_value=None):
        with pytest.raises(ImportError, match="Could not load spec for"):
            item.runtest()

    # 2. spec.loader is None
    mock_spec = SimpleNamespace(loader=None)
    with patch("importlib.util.spec_from_file_location", return_value=mock_spec):
        with pytest.raises(ImportError, match="Could not load spec for"):
            item.runtest()


def test_docstring_test_item_runtest_module_exec_error(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """DocstringTestItem.runtest raises RuntimeError when module execution fails."""
    py_file = tmp_path / "broken_exec.py"
    py_file.write_text(
        "raise ValueError('Import failed on import')\n", encoding="utf-8"
    )
    parent_file = PythonDocstringFile.from_parent(request.session, path=py_file)

    item = DocstringTestItem.from_parent(
        parent_file, name="broken_docstring", lineno=1, blocks=[]
    )

    with pytest.raises(
        RuntimeError,
        match="Error executing module broken_exec: Import failed on import",
    ):
        item.runtest()


def test_docstring_test_item_runtest_failure(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """DocstringTestItem.runtest raises AsciiDocTestFailure on test mismatch."""
    py_file = tmp_path / "fail_doc.py"
    py_file.write_text("def fn(): pass\n", encoding="utf-8")
    parent_file = PythonDocstringFile.from_parent(request.session, path=py_file)

    block = MockBlock(
        content=">>> 1 + 1\n999\n",
        is_interactive=True,
        line_number=2,
        attributes={"test": True},
    )
    item = DocstringTestItem.from_parent(
        parent_file, name="fn_docstring", lineno=2, blocks=[block]
    )

    with pytest.raises(AsciiDocTestFailure):
        item.runtest()


def test_docstring_test_item_repr_failure(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """DocstringTestItem.repr_failure handles AsciiDocTestFailure vs generic exceptions."""
    py_file = tmp_path / "item.py"
    py_file.write_text("x = 1\n", encoding="utf-8")
    parent_file = PythonDocstringFile.from_parent(request.session, path=py_file)
    item = DocstringTestItem.from_parent(
        parent_file, name="item_docstring", lineno=1, blocks=[]
    )

    # 1. AsciiDocTestFailure
    try:
        raise AsciiDocTestFailure("Mismatch in docstring at line 10")
    except AsciiDocTestFailure:
        excinfo1 = ExceptionInfo.from_current()

    repr1 = item.repr_failure(excinfo1)
    assert isinstance(repr1, str)
    assert "Mismatch in docstring at line 10" in repr1

    # 2. Generic TypeError
    try:
        raise TypeError("Invalid argument types")
    except TypeError:
        excinfo2 = ExceptionInfo.from_current()

    repr2 = item.repr_failure(excinfo2)
    assert "Invalid argument types" in str(repr2)


def test_docstring_test_item_reportinfo(
    tmp_path: pathlib.Path, request: pytest.FixtureRequest
) -> None:
    """DocstringTestItem.reportinfo returns path, lineno, and formatted name."""
    py_file = tmp_path / "report_test.py"
    py_file.write_text("def my_func(): pass\n", encoding="utf-8")
    parent_file = PythonDocstringFile.from_parent(request.session, path=py_file)
    item = DocstringTestItem.from_parent(
        parent_file, name="my_func_docstring", lineno=42, blocks=[]
    )

    path, lineno, name = item.reportinfo()
    assert path == py_file
    assert lineno == 42
    assert name == "Python Docstring: my_func_docstring"
