# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
sys.path.insert(0, os.path.abspath('..'))

# Tools for importing snscrape at build time
# Avoid name conflict with sphinx configuration variable "version"
from importlib import import_module
from importlib.metadata import metadata


# -- Project information -----------------------------------------------------

# Project name
project = 'snscrape'

# Metadata
_metadata = metadata(project)

# Version in format 0.4.0.20211208
release = _metadata['version']
author = _metadata['author']

_major, _minor, _patch, _yyyymmdd = release.split('.')

YEAR = _yyyymmdd[0:4]
copyright = f'{YEAR}, {author}'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.napoleon',
    'sphinx.ext.autodoc',
	'sphinx.ext.autosummary',
    # 'sphinx_autodoc_typehints'
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Custom extension options ------------------------------------------------

# Put type hint in description instead of signature
# Note: the docstrings are overridden if autodoc_typehints is used
autodoc_typehints = 'description'

# Set 'both' to use both class and __init__ docstrings.
autoclass_content = 'both'

# Might want to look at it:
# https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#confval-autodoc_type_aliases
# autodoc_type_aliases = {}

# Turn on autosummary
autosummary_generate = True

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'nature'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']