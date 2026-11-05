"""Checks that styles.css takes its colours and fonts from tokens.css."""

from pathlib import Path
import re
import unittest


WEB = Path(__file__).resolve().parents[1] / "app/web"
COLOR_LITERAL = re.compile(
    r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(|:\s*(?:white|black|red|green|blue|gray|grey|silver)\s*;"
)


def read(name):
    return (WEB / name).read_text(encoding="utf-8")


def declarations(css):
    """Each `property: value` in the CSS, with comments removed and with the line it starts on."""
    css = re.sub(r"/\*.*?\*/", lambda match: "\n" * match.group(0).count("\n"), css, flags=re.S)
    for number, line in enumerate(css.splitlines(), 1):
        match = re.match(r"\s*([\w-]+)\s*:\s*(.+?);?\s*$", line)
        if match and not line.lstrip().startswith("@"):
            yield number, match.group(1), match.group(2)


def script_files():
    return [WEB / "app.js", WEB / "brand.js", *sorted((WEB / "views").glob("*.js"))]


class TokenTests(unittest.TestCase):
    def setUp(self):
        self.styles = read("styles.css")
        self.tokens = dict((name, value) for _, name, value in declarations(read("tokens.css")) if name.startswith("--"))

    def test_styles_have_no_color_literals(self):
        for number, prop, value in declarations(self.styles):
            with self.subTest(line=number):
                self.assertIsNone(COLOR_LITERAL.search(prop + ": " + value + ";"), f"styles.css:{number}: {value}")

    def test_styles_have_no_font_stacks(self):
        for number, prop, value in declarations(self.styles):
            if prop in ("font-family", "font"):
                with self.subTest(line=number):
                    self.assertRegex(value, r"^(var\(--font-[\w-]+\)|inherit)$", f"styles.css:{number}")

    def test_styles_use_only_defined_tokens(self):
        set_in_styles = {prop for _, prop, _ in declarations(self.styles) if prop.startswith("--")}
        set_by_views = {"--weeks"}
        for number, _, value in declarations(self.styles):
            for name in re.findall(r"var\((--[\w-]+)", value):
                with self.subTest(line=number, token=name):
                    self.assertIn(name, set(self.tokens) | set_in_styles | set_by_views)

    def test_scripts_have_no_color_literals(self):
        for path in script_files():
            with self.subTest(file=path.name):
                self.assertIsNone(COLOR_LITERAL.search(path.read_text(encoding="utf-8")))

    def test_index_loads_tokens_before_styles(self):
        index = read("index.html")
        self.assertLess(index.index('href="tokens.css"'), index.index('href="styles.css"'))


class BrandTests(unittest.TestCase):
    def setUp(self):
        self.brand = read("brand.js")

    def value(self, key):
        match = re.search(r"^\s*(?:const )?" + key + r"\s*[:=]\s*'([^']+)'", self.brand, re.M)
        self.assertIsNotNone(match, f"brand.js has no {key}")
        return match.group(1)

    def test_index_title_matches_brand(self):
        title = re.search(r"<title>(.*?)</title>", read("index.html")).group(1)
        self.assertEqual(title, self.value("shortName") + " " + self.value("productName"))


if __name__ == "__main__":
    unittest.main()
