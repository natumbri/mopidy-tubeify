****************************
Mopidy-Tubeify
****************************

.. image:: https://img.shields.io/pypi/v/Mopidy-Tubeify
    :target: https://pypi.org/project/Mopidy-Tubeify/
    :alt: Latest PyPI version

.. image:: https://img.shields.io/github/workflow/status/natumbri/mopidy-tubeify/CI
    :target: https://github.com/natumbri/mopidy-tubeify/actions
    :alt: CI build status

.. image:: https://img.shields.io/codecov/c/gh/natumbri/mopidy-tubeify
    :target: https://codecov.io/gh/natumbri/mopidy-tubeify
    :alt: Test coverage

Mopidy extension for playing music service playlists using mopidy-youtube


Installation
============

Install by running::

    python3 -m pip install https://github.com/natumbri/mopidy-tubeify/archive/master.zip
    (TODO: python3 -m pip install Mopidy-Tubeify)

TODO: See https://mopidy.com/ext/tubeify/ for alternative installation methods.


Configuration
=============

Before starting Mopidy, you must add configuration for
Mopidy-Tubeify to your Mopidy configuration file::

    [tubeify]
    enabled = true

    applemusic_playlists =
      apple_playlist_id_1
      ...
      apple_playlist_id_n

Where apple_playlist_id_1 ... n are each an apple music playlist id, which can be found in an apple music url::

    https://[apple url]/playlist/{apple_playlist_id}


    spotify_users = 
      spotify_user_id_1
      ...
      spotify_user_id_n

Where spotify_user_id_1 ... n are each a spotify user id, which can be found in a spotify url::

    https://open.spotify.com/user/{spotify_user_id}


    tidal_playlists =
      tidal_playlist_id_1
      ...
      tidal_playlist_id_n

Where tidal_playlist_id_1 ... n are each a tidal music playlist id, which can be found in an tidal url::

    https://[tidal url]/playlist/{tidal_playlist_id}


Project resources
=================

- `Source code <https://github.com/natumbri/mopidy-tubeify>`_
- `Issue tracker <https://github.com/natumbri/mopidy-tubeify/issues>`_
- `Changelog <https://github.com/natumbri/mopidy-tubeify/blob/master/CHANGELOG.rst>`_


Credits
=======

- Original author: `Nik Tumbri <https://github.com/natumbri>`__
- Current maintainer: `Nik Tumbri <https://github.com/natumbri>`__
- `Contributors <https://github.com/natumbri/mopidy-tubeify/graphs/contributors>`_
