import json
import re

import pykka
import requests
from cachetools import TTLCache, cached
from mopidy import backend, httpclient
from mopidy.models import Ref
from ytmusicapi import YTMusic

from mopidy_tubeify import Extension, logger
from mopidy_tubeify.apple import Apple
from mopidy_tubeify.data import extract_playlist_id, extract_user_id
from mopidy_tubeify.spotify import Spotify
from mopidy_tubeify.tidal import Tidal


class TubeifyBackend(pykka.ThreadingActor, backend.Backend):
    def __init__(self, config, audio):
        super().__init__()
        self.config = config
        self.library = TubeifyLibraryProvider(backend=self)
        self.applemusic_playlists = config["tubeify"]["applemusic_playlists"]
        self.spotify_users = config["tubeify"]["spotify_users"]
        self.spotify_playlists = config["tubeify"]["spotify_playlists"]
        self.tidal_playlists = config["tubeify"]["tidal_playlists"]
        self.uri_schemes = ["tubeify"]
        self.user_agent = "{}/{}".format(Extension.dist_name, Extension.version)
        self.ytmusic = YTMusic()

    def on_start(self):
        proxy = httpclient.format_proxy(self.config["proxy"])
        headers = {"user-agent": httpclient.format_user_agent(self.user_agent)}
        self.services = []
        if self.applemusic_playlists:
            self.library.applemusic = Apple(proxy, headers)
            self.library.applemusic.ytmusic = self.ytmusic
            self.services.append(
                {"service_uri": "applemusic", "service_name": "Apple Music"}
            )
        if self.spotify_users or self.spotify_playlists:
            self.library.spotify = Spotify(proxy, headers)
            self.library.spotify.ytmusic = self.ytmusic
            self.services.append(
                {"service_uri": "spotify", "service_name": "Spotify"}
            )
        if self.tidal_playlists:
            self.library.tidal = Tidal()
            self.library.tidal.session = requests.Session()
            self.library.tidal.ytmusic = self.ytmusic
            self.services.append(
                {"service_uri": "tidal", "service_name": "Tidal"}
            )


class TubeifyLibraryProvider(backend.LibraryProvider):

    """
    Called when root_directory is set to [insert description]
    When enabled makes possible to browse the users listed in
    config and to browse their public playlists and the
    separate tracks those playlists.
    """

    root_directory = Ref.directory(uri="tubeify:browse", name="Tubeify")

    cache_max_len = 4000
    cache_ttl = 21600

    tubeify_cache = TTLCache(maxsize=cache_max_len, ttl=cache_ttl)

    @cached(cache=tubeify_cache)
    def browse(self, uri):

        # if we're browsing, return a list of directories
        if uri == "tubeify:browse":
            directoryrefs = [
                Ref.directory(
                    uri="tubeify:all:users", name="All Service Users"
                ),
                Ref.directory(
                    uri="tubeify:all:playlists", name="All Service Playlists"
                ),
            ]
            directoryrefs.extend(
                [
                    Ref.directory(
                        uri=f"tubeify:{service['service_uri']}:root",
                        name=service["service_name"],
                    )
                    for service in self.backend.services
                ]
            )
            return directoryrefs

        match = re.match(r"tubeify:(?P<service>.+):(?P<kind>.+)$", uri)

        if match:
            if match["service"] == "all":
                selected_services = self.backend.services
            else:
                selected_services = [
                    next(
                        (
                            service
                            for service in self.backend.services
                            if service["service_uri"] == match["service"]
                        ),
                        None,
                    )
                ]

        if match and match["kind"] == "root":
            directoryrefs = []
            for selected_service in selected_services:

                directoryrefs.append(
                    Ref.directory(
                        uri=f"tubeify:{selected_service['service_uri']}:home",
                        name=f"{selected_service['service_name']} Homepage",
                    )
                )

                for list_type in ["users", "playlists"]:
                    if getattr(
                        self.backend,
                        f"{selected_service['service_uri']}_{list_type}",
                        None,
                    ):
                        directoryrefs.append(
                            Ref.directory(
                                uri=f"tubeify:{selected_service['service_uri']}:{list_type}",
                                name=f"{selected_service['service_name']} {list_type}",
                            )
                        )
            return directoryrefs

        elif match and match["kind"] == "home":
            playlistrefs = []
            for selected_service in selected_services:
                service_method = getattr(
                    self, selected_service["service_uri"], None
                )
                playlists = service_method.get_service_homepage()
                playlistrefs.extend(
                    [
                        Ref.directory(
                            uri=f"tubeify:{selected_service['service_uri']}_playlist:{playlist['id']}",
                            name=playlist["name"],
                        )
                        for playlist in playlists
                        if playlist["id"]
                    ]
                )

            return playlistrefs

        # if we're looking at service playlists or users
        # get the details and return a list
        elif match and match["kind"] in ["users", "playlists"]:
            refs = []
            for selected_service in selected_services:
                service_method = getattr(
                    self, selected_service["service_uri"], None
                )
                get_details_method = getattr(
                    service_method, f'get_{match["kind"]}_details', None
                )
                listoflists = getattr(
                    self.backend,
                    f"{selected_service['service_uri']}_{match['kind']}",
                    [],
                )
                items = get_details_method(listoflists)
                refs.extend(
                    [
                        Ref.directory(
                            uri=(
                                f"tubeify:"
                                f"{selected_service['service_uri']}_"
                                f"{match['kind'][:-1]}:"
                                f"{item['id']}"
                            ),
                            name=item["name"],
                        )
                        for item in items
                    ]
                )
            return refs

        # if we're looking at a user, return a list of the user's playlists
        elif extract_user_id(uri):
            service, user_uri = extract_user_id(uri)
            logger.debug(f"browse {service} user {user_uri}")
            playlistrefs = []
            service_method = getattr(self, service, None)
            playlists = service_method.get_user_playlists(user_uri)
            playlistrefs = [
                Ref.directory(
                    uri=f"tubeify:{service}_playlist:{playlist['id']}",
                    name=playlist["name"],
                )
                for playlist in playlists
                if playlist["id"]
            ]
            return playlistrefs

        # if we're looking at a playlist, return a list of the playlist's tracks
        elif extract_playlist_id(uri):
            service, playlist_uri = extract_playlist_id(uri)
            logger.debug(f"browse {service} playlist {playlist_uri}")
            trackrefs = []
            service_method = getattr(self, service, None)
            tracks = service_method.get_playlist_tracks(playlist_uri)

            trackrefs = [
                Ref.track(
                    uri=f"yt:video:{track['videoId']}",
                    name=track["title"],
                )
                for track in tracks
                if "videoId" in track
            ]

            # include ytmusic data for all tracks as preload data in the uri
            # for the first track.  There is surely a better way to do this.
            # It breaks the first track in the musicbox_webclient
            first_track = [
                track
                for track in tracks
                if "videoId" in track
                and f"yt:video:{track['videoId']}" == trackrefs[0].uri
            ][0]

            trackrefs[0] = Ref.track(
                uri=(
                    f"yt:video:{first_track['videoId']}"
                    f":preload:"
                    f"{json.dumps([track for track in tracks if track is not None])}"
                ),
                name=first_track["title"],
            )
            return trackrefs

        else:
            logger.warn(f"There was a problem with uri {uri}")
