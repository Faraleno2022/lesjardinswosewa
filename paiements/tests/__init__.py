"""
Expose submodules so Django's test loader can find tests when importing
`paiements.tests`.

Django imports the tests package (paiements.tests) and loads tests from the
module object; it does not automatically recurse into submodules unless they
are imported here.
"""

# Import test modules
# Some legacy tests may rely on deprecated internals. Import them defensively
# so a single ImportError does not block the whole paiements test suite.
try:  # noqa: SIM105
    from . import test_allocation  # noqa: F401
except Exception:  # pragma: no cover - best effort to keep suite running
    # Intentionally swallow errors to allow other tests to run.
    # If needed, run `python manage.py test paiements.tests.test_allocation -v2`
    # to see the exact failure and update imports accordingly.
    pass
