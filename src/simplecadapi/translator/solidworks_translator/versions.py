"""Version contract shared by the compiler and standalone COM scripts.

Keep this module self-contained: its source is embedded in generated scripts.
"""

DEFAULT_SOLIDWORKS_VERSION = "2025"
SOLIDWORKS_API_MAJOR_BY_VERSION = {"2023": 31, "2025": 33}
SUPPORTED_SOLIDWORKS_VERSIONS = tuple(SOLIDWORKS_API_MAJOR_BY_VERSION)
SOLIDWORKS_PROGID_BY_VERSION = {
    version: "SldWorks.Application.%d" % major
    for version, major in SOLIDWORKS_API_MAJOR_BY_VERSION.items()
}


def normalize_solidworks_version(version):
    key = str(version).strip()
    if key not in SOLIDWORKS_API_MAJOR_BY_VERSION:
        raise ValueError(
            "Unsupported SolidWorks version %r; supported versions: %r"
            % (version, SUPPORTED_SOLIDWORKS_VERSIONS)
        )
    return key


def _solidworks_progid(version):
    return SOLIDWORKS_PROGID_BY_VERSION[normalize_solidworks_version(version)]


def _verify_solidworks_revision(version, revision):
    key = normalize_solidworks_version(version)
    expected = SOLIDWORKS_API_MAJOR_BY_VERSION[key]
    try:
        actual = int(str(revision).strip().split(".", 1)[0])
    except (ValueError, TypeError):
        raise RuntimeError("SolidWorks returned an invalid RevisionNumber: %r" % revision)
    if actual != expected:
        raise RuntimeError(
            "Requested SolidWorks %s (%s), but connected RevisionNumber is %r; "
            "expected API major %s"
            % (key, _solidworks_progid(key), revision, expected)
        )
    return actual
