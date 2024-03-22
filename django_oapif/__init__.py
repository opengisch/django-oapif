try:
    from .__version__ import __version__, __version_tuple__
except ImportError:
    __version__ = "0.0.0.dev"
    __version_tuple__ = (0, 0, 0, "dev")
