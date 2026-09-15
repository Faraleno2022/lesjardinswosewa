from pathlib import Path

from django.conf import settings
from django.template import engines
from django.test import SimpleTestCase


class SyntaxeTemplatesTests(SimpleTestCase):
    def test_tous_les_templates_html_compilent(self):
        engine = engines["django"]
        for folder in settings.TEMPLATES[0]["DIRS"]:
            for path in Path(folder).rglob("*.html"):
                with self.subTest(template=str(path.relative_to(folder))):
                    engine.from_string(path.read_text(encoding="utf-8-sig"))
