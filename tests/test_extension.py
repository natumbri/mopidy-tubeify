from mopidy_tubeify import Extension

# from mopidy_spotitube import frontend as frontend_lib


def test_get_default_config():
    ext = Extension()

    config = ext.get_default_config()

    assert "[tubeify]" in config
    assert "enabled = true" in config


def test_get_config_schema():
    ext = Extension()

    schema = ext.get_config_schema()

    # TODO Test the content of your config schema
    assert "applemusic_playlists" in schema
    assert "spotify_users" in schema
    assert "tidal_playlists" in schema


# TODO Write more tests
