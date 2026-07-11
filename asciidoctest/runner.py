import doctest
import io
import traceback
from typing import List, Dict, Any
from asciidocstring.visitors import TestBlock

class AsciiDocTestFailure(AssertionError):
    """Exception raised when an asciidoc test block execution fails."""
    pass

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

def run_test_blocks(blocks: List[Any], shared_globals: Dict[str, Any]) -> None:
    """
    Executes a sequence of test blocks under a shared globals namespace.
    
    Interactive blocks are parsed and run using doctest.DocTestParser.
    Non-interactive blocks are compiled and run via exec().
    """
    optionflags = doctest.ELLIPSIS | doctest.IGNORE_EXCEPTION_DETAIL
    
    for block in blocks:
        if block.is_interactive:
            # Parse interactive session
            parser = doctest.DocTestParser()
            test = parser.get_doctest(
                block.content,
                shared_globals,
                name=f"block_at_line_{block.line_number}",
                filename="<string>",
                lineno=block.line_number
            )
            
            # Execute interactive doctest
            runner = CustomDocTestRunner(optionflags=optionflags)
            runner.run(test, clear_globs=False)
            
            # Propagate updated variables back to shared_globals for sequential blocks
            shared_globals.update(test.globs)
            
            if runner.test_failures:
                first_fail_msg = runner.test_failures[0][2]
                raise AsciiDocTestFailure(
                    f"Test block failure at line {block.line_number}:\n{first_fail_msg}"
                )
        else:
            # Execute non-interactive raw Python block
            try:
                # Compile code to get better tracebacks and exec in shared_globals
                # Note: We append a newline to avoid compilation syntax errors if missing trailing lines
                code_content = block.content
                if not code_content.endswith("\n"):
                    code_content += "\n"
                compiled_code = compile(
                    code_content,
                    f"<block_at_line_{block.line_number}>",
                    "exec"
                )
                exec(compiled_code, shared_globals)
            except AssertionError as ae:
                tb = traceback.format_exc()
                raise AsciiDocTestFailure(
                    f"Assertion failed in non-interactive block at line {block.line_number}:\n{tb}"
                )
            except Exception as e:
                tb = traceback.format_exc()
                raise AsciiDocTestFailure(
                    f"Exception raised in non-interactive block at line {block.line_number}:\n{tb}"
                )
