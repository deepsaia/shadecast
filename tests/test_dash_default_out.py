"""A default dashboard build writes outside the tracked tree, so nothing generated reaches git."""

from shadecast import dash_cli


def test_the_default_bundle_directory_is_under_the_ignored_out_directory():
    assert dash_cli.DEFAULT_OUT.parts[0] == "out"
