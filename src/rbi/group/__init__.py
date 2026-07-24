"""Stage 8: group. Link the same substantive change across entity types (§6.7).

Within a single issued_date, operations whose new_text is near-identical are the
same policy landing at different clause coordinates (RRB 68C == LAB 119C). The
stored similarity score — ~0.957 for the SNFA pair — is the reference value.
"""
from .models import ChangeGroup, ChangeGroupMember, OpRef
from .build import group_ops
from .similarity import cosine, word_similarity

__all__ = [
    "OpRef",
    "ChangeGroup",
    "ChangeGroupMember",
    "group_ops",
    "word_similarity",
    "cosine",
]
