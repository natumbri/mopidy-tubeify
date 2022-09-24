import json
import re

import pykka
from cachetools import TTLCache, cached
from mopidy import backend, httpclient
from mopidy.models import Ref
from ytmusicapi import YTMusic

from mopidy_tubeify import Extension, logger
from mopidy_tubeify.allmusic import AllMusic
from mopidy_tubeify.amrap import Amrap
from mopidy_tubeify.apple import Apple
from mopidy_tubeify.data import extract_playlist_id, extract_user_id
from mopidy_tubeify.discogs import Discogs
from mopidy_tubeify.kcrw import KCRW
from mopidy_tubeify.kexp import KEXP
from mopidy_tubeify.nme import NME
from mopidy_tubeify.pitchfork import Pitchfork
from mopidy_tubeify.spotify import Spotify
from mopidy_tubeify.tidal import Tidal
from mopidy_tubeify.tripler import TripleR


class TubeifyBackend(pykka.ThreadingActor, backend.Backend):
    def __init__(self, config, audio):
        super().__init__()
        self.config = config
        self.library = TubeifyLibraryProvider(backend=self)
        self.applemusic_playlists = config["tubeify"]["applemusic_playlists"]
        self.applemusic_users = config["tubeify"]["applemusic_users"]
        self.spotify_users = config["tubeify"]["spotify_users"]
        self.spotify_playlists = config["tubeify"]["spotify_playlists"]
        self.tidal_playlists = config["tubeify"]["tidal_playlists"]
        self.uri_schemes = ["tubeify"]
        self.user_agent = "{}/{}".format(Extension.dist_name, Extension.version)

    def on_start(self):
        proxy = httpclient.format_proxy(self.config["proxy"])

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 6.1) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/80.0.3987.149 Safari/537.36 "
                f"{httpclient.format_user_agent(self.user_agent)}"
            )
        }

        self.ytmusic = YTMusic()

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
            # Tidal seems to be fussy about the User-Agent, and requires "Accept"
            self.library.tidal = Tidal(
                proxy,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 6.1) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/80.0.3987.149 Safari/537.36"
                    ),
                    "Accept": "*/*",
                },
            )
            self.library.tidal.ytmusic = self.ytmusic
            self.services.append(
                {"service_uri": "tidal", "service_name": "Tidal"}
            )

        self.library.allmusic = AllMusic(proxy, headers)
        self.library.allmusic.ytmusic = self.ytmusic
        self.services.append(
            {"service_uri": "allmusic", "service_name": "AllMusic"}
        )

        self.library.discogs = Discogs(proxy, headers)
        self.library.discogs.ytmusic = self.ytmusic
        self.services.append(
            {"service_uri": "discogs", "service_name": "Discogs"}
        )

        self.library.kcrw = KCRW(proxy, headers)
        self.library.kcrw.ytmusic = self.ytmusic
        self.services.append(
            {"service_uri": "kcrw", "service_name": "KCRW 89.9FM"}
        )

        self.library.kexp = KEXP(proxy, headers)
        self.library.kexp.ytmusic = self.ytmusic
        self.services.append(
            {"service_uri": "kexp", "service_name": "KEXP 90.3FM"}
        )

        self.library.nme = NME(proxy, headers)
        self.library.nme.ytmusic = self.ytmusic
        self.services.append(
            {"service_uri": "nme", "service_name": "NME Reviewed Albums"}
        )

        self.library.pitchfork = Pitchfork(proxy, headers)
        self.library.pitchfork.ytmusic = self.ytmusic
        self.services.append(
            {"service_uri": "pitchfork", "service_name": "Pitchfork"}
        )

        self.library.tripler = TripleR(proxy, headers)
        self.library.tripler.ytmusic = self.ytmusic
        self.services.append(
            {"service_uri": "tripler", "service_name": "3RRR 102.7FM"}
        )

        # Amrap() is a generic client for AMRAP Radio Stations
        # see https://radiopages.info/ for a list of them
        self.library.pbsfm = Amrap(proxy, headers, stationId="3pbs")
        self.library.pbsfm.ytmusic = self.ytmusic
        self.services.append(
            {
                "service_uri": "pbsfm",
                "service_name": "3PBS 106.7FM",
            }
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
        def get_refs(kind, selected_services, listoflists=None):
            refs = []

            # need to fix this
            if len(selected_services) > 1 and listoflists:
                logger.error(
                    f"listoflists only works for a single service, "
                    f"not {selected_services}"
                )

            for selected_service in selected_services:
                service_method = getattr(
                    self, selected_service["service_uri"], None
                )
                get_details_method = getattr(
                    service_method, f"get_{kind}_details", None
                )

                if not listoflists:
                    listoflists = getattr(
                        self.backend,
                        f"{selected_service['service_uri']}_{kind}",
                        [],
                    )

                items = get_details_method(listoflists)

                # need to fix this, too; listoflists reset to None
                # for each service in the list of selected services
                listoflists = None

                refs.extend(
                    [
                        Ref.directory(
                            uri=(
                                f"tubeify:"
                                f"{selected_service['service_uri']}_"
                                f"{kind[:-1]}:"
                                f"{item['id']}"
                            ),
                            name=item["name"],
                        )
                        for item in items
                    ]
                )
            return refs

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

            servicerefs = [
                Ref.directory(
                    uri=f"tubeify:{service['service_uri']}:root",
                    name=service["service_name"],
                )
                for service in self.backend.services
            ]

            directoryrefs.extend(
                sorted(servicerefs, key=lambda x: x.name.lower())
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
            return get_refs(
                kind=match["kind"], selected_services=selected_services
            )

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
            service_method = getattr(self, service, None)

            # deal with things that are flagged as lists of lists
            # (eg, playlists or albums) not lists of tracks
            listoflists_match = re.match(
                r"^listoflists\-(?P<listoflists>.+)$", playlist_uri
            )
            if listoflists_match:
                return get_refs(
                    "playlists",
                    [{"service_uri": service}],
                    listoflists=[listoflists_match["listoflists"]],
                )

            tracks = service_method.get_playlist_tracks(playlist_uri)
            good_tracks = []
            good_albums = []
            trackrefs = []

            if tracks:
                good_tracks = [
                    track
                    for track in tracks
                    if "videoId" in track
                    and track["videoId"]
                    and "title" in track
                    and track["title"]
                ]

                good_albums = [
                    album
                    for album in tracks
                    if "type" in album
                    and album["type"] == "Album"
                    and album["browseId"]
                    and "title" in album
                    and album["title"]
                ]

            if good_tracks:
                trackrefs.extend(
                    [
                        Ref.track(
                            uri=f"yt:video:{track['videoId']}",
                            name=track["title"],
                        )
                        for track in good_tracks
                        # if "videoId" in track and track["videoId"]
                    ]
                )

                # include ytmusic data for all tracks as preload data in the uri
                # for the first track.  There is surely a better way to do this.
                # It breaks the first track in the musicbox_webclient
                first_track = [
                    track
                    for track in good_tracks
                    if f"yt:video:{track['videoId']}" == trackrefs[0].uri
                ][0]

                trackrefs[0] = Ref.track(
                    uri=(
                        f"yt:video:{first_track['videoId']}"
                        f":preload:"
                        f"{json.dumps([track for track in good_tracks if track is not None])}"
                    ),
                    name=first_track["title"],
                )

            if good_albums:
                trackrefs.extend(
                    [
                        Ref.album(
                            uri=f"yt:playlist:{album['browseId']}",
                            name=album["title"],
                        )
                        for album in good_albums
                    ]
                )

            return trackrefs

        else:
            logger.warn(f"There was a problem with uri {uri}")

        return []
