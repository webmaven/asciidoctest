import doctest
import traceback
from typing import Any

from asciidoctest.parser import (
    block_get_shared_context,
    block_has_reset_marker,
    block_has_shared_marker,
    block_has_test_marker,
)


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
    Supports section boundaries, named context scopes, and explicit reset markers.
    """
    optionflags = doctest.ELLIPSIS | doctest.IGNORE_EXCEPTION_DETAIL
    initial_globals = shared_globals.copy()
    named_contexts: dict[str, dict[str, Any]] = {}
    current_section_id = None

    for block in blocks:
        block_section_id = getattr(block, "attributes", {}).get("__section_id__")
        if (
            block_section_id is not None
            and current_section_id is not None
            and block_section_id != current_section_id
        ):
            shared_globals.clear()
            shared_globals.update(initial_globals.copy())
            named_contexts.clear()
        if block_section_id is not None:
            current_section_id = block_section_id

        has_reset = block_has_reset_marker(block)
        if has_reset:
            shared_globals.clear()
            shared_globals.update(initial_globals.copy())
            named_contexts.clear()

        has_test = block_has_test_marker(block)
        has_shared = block_has_shared_marker(block)
        context_name = block_get_shared_context(block)

        if context_name:
            if context_name not in named_contexts:
                named_contexts[context_name] = initial_globals.copy()
            target_shared = named_contexts[context_name]
        else:
            target_shared = shared_globals

        if has_shared and has_test:
            test_globals = target_shared.copy()
            should_write_back = False
        elif has_shared or context_name:
            test_globals = target_shared
            should_write_back = True
        else:
            test_globals = initial_globals.copy()
            should_write_back = False

        if getattr(block, "is_interactive", False):
            parser = doctest.DocTestParser()
            test = parser.get_doctest(
                block.content,
                test_globals,
                name=f"block_at_line_{block.line_number}",
                filename="<string>",
                lineno=block.line_number,
            )
            runner = CustomDocTestRunner(optionflags=optionflags)
            runner.run(test, clear_globs=False)

            if should_write_back:
                target_shared.update(test.globs)

            if runner.test_failures:
                first_fail_msg = runner.test_failures[0][2]
                raise AsciiDocTestFailure(
                    f"Test block failure at line {block.line_number}:\n{first_fail_msg}"
                )
        else:
            try:
                code_content = block.content
                if not code_content.endswith("\n"):
                    code_content += "\n"
                compiled_code = compile(
                    code_content, f"<block_at_line_{block.line_number}>", "exec"
                )
                exec(compiled_code, test_globals)
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
