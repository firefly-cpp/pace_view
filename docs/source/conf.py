import os, sys
sys.path.insert(0, os.path.abspath('..\\..'))

extensions = ["sphinx.ext.autodoc", "sphinx.ext.napoleon", "sphinx.ext.viewcode", "myst_parser"]
html_theme = "sphinx_rtd_theme"

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Physics-Augmented Contextual Explainer and Visual Interface for Endurance Workflows'
copyright = '2026, Iztok Fister Jr., Sebastian Gürtl, Sebastian Pack, Andreas Holzinger'
author = 'Iztok Fister Jr., Sebastian Gürtl, Sebastian Pack, Andreas Holzinger'
release = '0.1'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

templates_path = ['_templates']
exclude_patterns = []

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
