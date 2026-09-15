"""Expose les balises de charte depuis une application Django installee."""

from ecole_moderne.templatetags.branding import (  # noqa: F401
    register,
    school_document_branding,
)
