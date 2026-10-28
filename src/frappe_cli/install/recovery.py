"""Explain known failures without guessing destructive repairs."""


def explain(error) -> tuple[str, bool]:
    message = f"{error.message}\n{error.hint}".lower()
    if any(
        text in message
        for text in (
            "could not get lock",
            "unable to acquire",
            "waiting for cache lock",
        )
    ):
        return (
            "Another package operation is running. Let it finish, then retry. Do not remove its lock files.",
            True,
        )
    if any(
        text in message
        for text in (
            "temporary failure",
            "timed out",
            "connection reset",
            "could not resolve host",
            "network is unreachable",
        )
    ):
        return (
            "The network or package source is temporarily unavailable. Check connectivity, then retry.",
            True,
        )
    if any(
        text in message
        for text in ("unauthorized", "nxdomain", "dns problem", "challenge failed")
    ):
        return (
            "Check this domain's DNS and challenge reachability. Completed deployment steps are preserved.",
            False,
        )
    if any(
        text in message
        for text in ("access denied", "authentication failed", "incorrect password")
    ):
        return (
            "Check the supplied credentials. Resume setup to enter them again.",
            False,
        )
    if any(text in message for text in ("address already in use", "port is already")):
        return (
            "A required port is occupied. Inspect the existing service before changing its configuration.",
            False,
        )
    if any(text in message for text in ("no space left", "disk quota")):
        return "Free disk space on the target filesystem, then resume.", False
    return (
        "Inspect the details below. Existing files and completed steps are preserved.",
        False,
    )
