# This module is used by setup.py to pull the version below.
# WARNING: this approach will fail if we import anything here that
# we rely on setup.py to install.
# See that warning on Step 6 here:
# https://packaging.python.org/guides/single-sourcing-package-version/
# If we want to do imports here, there is a different approach.
__version__ = "0.1.2"

from .util import (
    fix_column_name,
    extract_mdb_table,
    fix_mdb_column_definition,
    get_mdb_column_definition,
)

__all__ = [
    "fix_column_name",
    "extract_mdb_table",
    "fix_mdb_column_definition",
    "get_mdb_column_definition",
]
