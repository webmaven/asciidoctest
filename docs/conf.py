import os
import sys

sys.path.insert(0, os.path.abspath(".."))

project = "asciidoctest"
copyright = "2026, Michael R. Bernstein"
author = "Michael R. Bernstein"
release = "0.2.0a2"

extensions = [
    "sphinx_asciidoctrine",
    "sphinx_rtd_theme",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

def setup(app):
    app.add_css_file("custom.css")
