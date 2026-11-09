"""Reference solver on clingo. Requires the optional dependency installed by pip install coom-lang[asp]."""

try:
    import clingo as _clingo  # noqa: F401
except ImportError as error:  # pragma: no cover
    raise ImportError("The COOM reference solver needs clingo. Install it with: pip install coom-lang[asp]") from error
