import doctest
import traceback
from typing import Any

from asciidoctest.parser import block_has_shared_marker, block_has_test_marker


class AsciiDocTestFailure(AssertionError):
    """Exception raised when an asciidoc test block execution fails."""

class CustomDocTestRunner(doctest.DocTestRunner):
    """A customized doctest runner that gathers failures in-memory."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_failures = []

    def report_failure(self, out, test, example, got):
        msg = (
            f"Failed example:\n    {example.source.strip()}\n"
            f"Expected:\n    {example.want.strip()}\n"
            f"Got:\n    {got.strip()}"
        )
        self.test_failures.append((example, got, msg))

    def report_unexpected_exception(self, out, test, example, exc_info):
        tb_str = "".join(traceback.format_exception(*exc_info))
        msg = (
            f"Failed example:\n    {example.source.strip()}\n"
            f"Unexpected Exception:\n{tb_str}"
        )
        self.test_failures.append((example, exc_info, msg))

def run_test_blocks(blocks: list[Any], shared_globals: dict[str, Any]) -> None:
    """
    Executes a sequence of test blocks under a unified, symmetric state model.
    
    1. 'test' only: Completely isolated (runs in a copy of initial_globals) and ephemeral.
    2. 'shared' only: Completely read-write and persistent in shared_globals.
    3. 'shared, test': Ephemeral copy of shared state (read-only snapshot at that point).
    """
    optionflags = doctest.ELLIPSIS | doctest.IGNORE_EXCEPTION_DETAIL
    
    # Capture a copy of the initial state at the start of document/docstring execution.
    # This allows 'test' only blocks to access pre-populated globals (like module-level scope
    # containing functions under test) while keeping them fully isolated from other blocks.
    initial_globals = shared_globals.copy()
    
    for block in blocks:
        # Resolve explicit test and shared markings
        has_test = block_has_test_marker(block)
        has_shared = block_has_shared_marker(block)
        
        # Classify and initialize execution namespace
        if has_shared and has_test:
            # Case A: 'shared, test' -> Ephemeral copy of shared state (read-only snapshot at that point)
            test_globals = shared_globals.copy()
            should_write_back = False
        elif has_shared:
            # Case B: 'shared' only -> Complete read-write and persistent
            test_globals = shared_globals
            should_write_back = True
        else:
            # Case C/D: 'test' only, or eager mode default -> Completely isolated from other blocks.
            # It starts with the clean, initial namespace copy.
            test_globals = initial_globals.copy()
            should_write_back = False
            
        if block.is_interactive:
            # Parse and run interactive session in test_globals
            parser = doctest.DocTestParser()
            test = parser.get_doctest(
                block.content,
                test_globals,
                name=f"block_at_line_{block.line_number}",
                filename="<string>",
                lineno=block.line_number
            )
            
            runner = CustomDocTestRunner(optionflags=optionflags)
            runner.run(test, clear_globs=False)
            
            # Save back variables if in Case B (shared only)
            if should_write_back:
                shared_globals.update(test.globs)
                
            if runner.test_failures:
                first_fail_msg = runner.test_failures[0][2]
                raise AsciiDocTestFailure(
                    f"Test block failure at line {block.line_number}:\n{first_fail_msg}"
                )
        else:
            # Execute non-interactive raw Python block
            try:
                # Compile code to get better tracebacks and exec in test_globals
                code_content = block.content
                if not code_content.endswith("\n"):
                    code_content += "\n"
                compiled_code = compile(
                    code_content,
                    f"<block_at_line_{block.line_number}>",
                    "exec"
                )
                exec(compiled_code, test_globals)
                
                # Save back variables if in Case B (shared only)
                if should_write_back:
                    # For script blocks, since test_globals is shared_globals,
                    # updates are already written back. But we can ensure it.
                    pass
            except AssertionError:
                tb = traceback.format_exc()
                raise AsciiDocTestFailure(
                    f"Assertion failed in non-interactive block at line {block.line_number}:\n{tb}"
                ) from None
            except Exception:
                tb = traceback.format_exc()
                raise AsciiDocTestFailure(
                    f"Exception raised in non-interactive block at line {block.line_number}:\n{tb}"
                ) from None
