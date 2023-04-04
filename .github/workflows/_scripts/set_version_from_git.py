import os
from pathlib import Path

LIBDIR = Path(__file__).parent.parent.parent.parent / "src" / "django_oapif"
INITDIR = LIBDIR / "__init__.py"

version_name = os.getenv("GITHUB_TAG").split("/")[2]

# read file
contents = INITDIR.read_text()

# replace contents
INITDIR.write_text(contents.replace("0.0.0", version_name, 1))
