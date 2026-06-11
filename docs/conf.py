"""Sphinx configuration for PalaceToolkit documentation."""

from __future__ import annotations

project = "PalaceToolkit"
author = "EpsilonForge"

extensions = [
    "myst_nb",
    "sphinx.ext.mathjax",
    "sphinx_copybutton",
    "sphinx_design",
]

source_suffix = {
    ".md": "myst-nb",
    ".ipynb": "myst-nb",
}

root_doc = "index"
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "**/.ipynb_checkpoints",
]

# MyST and notebook behavior
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "dollarmath",
    "html_admonition",
    "html_image",
    "linkify",
    "replacements",
    "substitution",
    "tasklist",
]

nb_execution_mode = "off"
nb_render_markdown_format = "myst"
suppress_warnings = ["myst.header"]

html_theme = "pydata_sphinx_theme"
html_title = "PalaceToolkit"
html_logo = "PalaceToolkit.png"
html_favicon = "PalaceToolkit.png"

html_theme_options = {
    "show_nav_level": 2,
    "navigation_with_keys": True,
    "logo": {
        "text": "PalaceToolkit",
    },
}

html_static_path = [
    "stylesheets",
    "javascripts",
]

html_css_files = ["interactive.css"]
html_js_files = [
    "https://cdnjs.cloudflare.com/ajax/libs/require.js/2.3.6/require.min.js",
    "mathjax.js",
]

mathjax3_config = {
    "tex": {
        "inlineMath": [["$", "$"], ["\\(", "\\)"]],
        "displayMath": [["$$", "$$"], ["\\[", "\\]"]],
        "processEscapes": True,
        "processEnvironments": True,
    },
    "options": {
        "ignoreHtmlClass": "tex2jax_ignore|mathjax_ignore",
    },
}
