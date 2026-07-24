"""Stage 7: apply. Walk verified operations -> materialise the clause timeline.

Pure-domain core (no DB): build_timeline + assert_no_overlap + resolve. The as-of
resolver is the date-flip demo (Definition of Done #1). Persistence of these
ClauseVersion rows to Postgres lives in rbi.db.sync.
"""
from .build import assert_no_overlap, build_timeline, make_sort_key
from .models import ClauseVersion, Resolution
from .resolve import resolve

__all__ = [
    "ClauseVersion",
    "Resolution",
    "build_timeline",
    "assert_no_overlap",
    "make_sort_key",
    "resolve",
]
