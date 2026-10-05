"""Guards for the oldest Python the README promises (3.9).

CI is the real check. These catch the known offenders locally, where only a
newer Python may be installed.
"""
import ast
import unittest

from helpers import REPO

SOURCES = sorted([*(REPO / "scripts").rglob("*.py"), *(REPO / "tests").rglob("*.py")])


class Python39Tests(unittest.TestCase):
    def test_path_write_text_is_never_given_newline(self):
        # Path.write_text(newline=...) arrived in Python 3.10.
        offenders = []
        for path in SOURCES:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "write_text"
                        and any(k.arg == "newline" for k in node.keywords)):
                    offenders.append(f"{path.relative_to(REPO).as_posix()}:{node.lineno}")
        self.assertEqual(offenders, [], "use store.write_text, which works on Python 3.9")

    def test_no_syntax_newer_than_3_9(self):
        for path in SOURCES:
            source = path.read_text(encoding="utf-8")
            try:
                ast.parse(source, feature_version=(3, 9))
            except SyntaxError as e:
                self.fail(f"{path.relative_to(REPO).as_posix()}:{e.lineno} needs a newer Python: {e.msg}")


if __name__ == "__main__":
    unittest.main()
