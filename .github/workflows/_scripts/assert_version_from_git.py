"""
This scripts ensures that the library was installed with the version corresponding to the current github tag
"""

import os
import sys
from pathlib import Path

LIBDIR = Path(__file__).parent.parent.parent.parent / "src" / "django_oapif"

sys.path.append(LIBDIR.parent)

import django_oapif  # noqa

version = django_oapif.__version__
tag = os.getenv("GITHUB_TAG")

assert (
    f"refs/heads/{version}" == tag or f"refs/tags/{version}" == tag
), f"Version mismatch : {version} != {tag}"
