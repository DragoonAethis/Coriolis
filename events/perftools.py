import re

SENTRY_FRONT_PAGE_URI_MATCHER = re.compile("[a-zA-Z0-9_-]+")

# BE CAREFUL IN THIS MODULE! THIS IS IMPORTED FROM PROJECT SETTINGS!
# You cannot reference most Django internals here, because the core
# module is still getting initialized.


def sentry_frontpage_spam_downsampler(context):
    """Determines the sampling rate at which we send traces and profiles
    to Sentry. This gets called before the request is fully set up, so
    you can only use the provided context, not any imported Django stuff."""
    transaction = context.get("transaction_context")
    wsgi_env = context.get("wsgi_environ")

    if not transaction or not wsgi_env:
        return True

    uri = wsgi_env.get("RAW_URI")
    assertions = [
        transaction.get("op") == "http.server",
        transaction.get("origin") == "auto.http.django",
        wsgi_env.get("REQUEST_METHOD") == "GET",
        wsgi_env.get("QUERY_STRING") == "",
        (uri == "/") or SENTRY_FRONT_PAGE_URI_MATCHER.fullmatch(uri.removeprefix("/event/").removesuffix("/")),
    ]

    if all(assertions):
        return 0.05

    return True


def show_pyinstrument(profile_passwords, request):
    """Determines if we should enable the in-browser profiler.
    Right now this is a simple"""
    if not profile_passwords or "profile" not in request.GET:
        return False

    return request.GET["profile"] in profile_passwords
