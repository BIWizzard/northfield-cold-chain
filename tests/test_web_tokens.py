"""Checks that the web app's look comes from tokens.css and its names from brand.js, so it can be reskinned."""

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

    def test_styles_use_roles_not_raw_primitives(self):
        # A token whose value is a colour literal or a font stack is a primitive. styles.css goes through the roles.
        primitives = {name for name, value in self.tokens.items()
                      if COLOR_LITERAL.search(": " + value + ";") or name.startswith("--font-stack-")}
        self.assertTrue(primitives)
        for number, _, value in declarations(self.styles):
            for name in re.findall(r"var\((--[\w-]+)", value):
                with self.subTest(line=number, token=name):
                    self.assertNotIn(name, primitives, f"styles.css:{number} uses a primitive")

    def test_styles_use_only_defined_tokens(self):
        set_in_styles = {prop for _, prop, _ in declarations(self.styles) if prop.startswith("--")}
        set_by_views = {"--weeks"}
        for number, _, value in declarations(self.styles):
            for name in re.findall(r"var\((--[\w-]+)", value):
                with self.subTest(line=number, token=name):
                    self.assertIn(name, set(self.tokens) | set_in_styles | set_by_views)

    def test_styles_size_with_tokens(self):
        # Pixel values only for 1px hairlines; media queries are skipped by declarations().
        for number, prop, value in declarations(self.styles):
            with self.subTest(line=number):
                self.assertEqual(re.findall(r"(?<![\w.-])-?(?!1px)[\d.]+px", value), [], f"styles.css:{number}: {value}")

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

    def test_brand_names_only_in_brand_js(self):
        names = [self.value(key) for key in ("companyName", "shortName", "productName", "fullProductName", "repoName")]
        files = [*script_files(), WEB / "index.html", WEB / "styles.css", WEB / "tokens.css"]
        for path in files:
            if path.name == "brand.js":
                continue
            text = path.read_text(encoding="utf-8")
            if path.name == "index.html":
                # The static title is the fallback until app.js sets brand.js's title.
                text = re.sub(r"<title>.*?</title>", "", text)
            for name in names:
                with self.subTest(file=path.name, name=name):
                    self.assertNotIn(name.lower(), text.lower())

    def test_index_title_matches_brand(self):
        title = re.search(r"<title>(.*?)</title>", read("index.html")).group(1)
        self.assertEqual(title, self.value("shortName") + " " + self.value("productName"))


if __name__ == "__main__":
    unittest.main()
