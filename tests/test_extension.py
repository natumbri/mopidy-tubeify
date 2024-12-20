from mopidy_tubeify import Extension
from ytmusicapi import YTMusic
from mopidy_tubeify.allmusic import AllMusic
from mopidy_tubeify.amrap import Amrap
from mopidy_tubeify.apple import Apple

# from mopidy_tubeify.bestlivealbums import BestLiveAlbums
from mopidy_tubeify.discogs import Discogs
from mopidy_tubeify.farout import FarOut
from mopidy_tubeify.kcrw import KCRW
from mopidy_tubeify.kexp import KEXP

# from mopidy_tubeify.lastfm import LastFM
from mopidy_tubeify.musicreviewworld import MusicReviewWorld
from mopidy_tubeify.nme import NME
from mopidy_tubeify.npr import NPR
from mopidy_tubeify.pitchfork import Pitchfork
from mopidy_tubeify.rollingstone import RollingStone
from mopidy_tubeify.spotify import Spotify
from mopidy_tubeify.tidal import Tidal
from mopidy_tubeify.tripler import TripleR
from mopidy_tubeify.whathifi import WhatHiFi

# from mopidy_spotitube import frontend as frontend_lib

import pytest

standard_services = [
    AllMusic,
    Apple,
    # BestLiveAlbums,
    Discogs,
    FarOut,
    KCRW,
    # KEXP,
    MusicReviewWorld,
    NME,
    NPR,
    Pitchfork,
    RollingStone,
    Spotify,
    TripleR,
    WhatHiFi,
]

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

@pytest.mark.parametrize("service", standard_services)
def test_homepage(service):
    headers = {
        "User-Agent": r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
    }

    scraper = service(None, headers, YTMusic())
    homepage = scraper.get_service_homepage()
    assert homepage
