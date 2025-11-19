"""Package marker for the project's `src` package.

Making `src` an importable package fixes test collection when running
`pytest` so tests can import modules like `src.utils`.
"""

__all__ = []
