import json
import re

import pykka
from cachetools import TTLCache, cached
from mopidy import backend, httpclient
from mopidy.models import Image, Ref
from ytmusicapi import YTMusic

from mopidy_tubeify import Extension, logger
from mopidy_tubeify.allmusic import AllMusic
from mopidy_tubeify.amrap import Amrap
from mopidy_tubeify.apple import Apple
from mopidy_tubeify.bestlivealbums import BestLiveAlbums
from mopidy_tubeify.data import extract_playlist_id, extract_user_id
from mopidy_tubeify.discogs import Discogs
from mopidy_tubeify.farout import FarOut
from mopidy_tubeify.kcrw import KCRW
from mopidy_tubeify.kexp import KEXP
from mopidy_tubeify.lastfm import LastFM
from mopidy_tubeify.musicreviewworld import MusicReviewWorld
from mopidy_tubeify.nme import NME
from mopidy_tubeify.npr import NPR
from mopidy_tubeify.pitchfork import Pitchfork
from mopidy_tubeify.rollingstone import RollingStone
from mopidy_tubeify.spotify import Spotify
from mopidy_tubeify.tidal import Tidal
from mopidy_tubeify.tripler import TripleR
from mopidy_tubeify.whathifi import WhatHiFi


class TubeifyBackend(pykka.ThreadingActor, backend.Backend):
    def __init__(self, config, audio):
        super().__init__()
        self.config = config
        self.library = TubeifyLibraryProvider(backend=self)
        self.applemusic_playlists = config["tubeify"]["applemusic_playlists"]
        self.applemusic_users = config["tubeify"]["applemusic_users"]
        self.lastfm_users = config["tubeify"]["lastfm_users"]
        self.lastfm_username = config["tubeify"]["lastfm_username"]
        self.lastfm_password = config["tubeify"]["lastfm_password"]
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

        standard_services = [
            AllMusic,
            Apple,
            BestLiveAlbums,
            Discogs,
            FarOut,
            KCRW,
            KEXP,
            MusicReviewWorld,
            NME,
            NPR,
            Pitchfork,
            RollingStone,
            Spotify,
            TripleR,
            WhatHiFi,
        ]

        self.services = {
            service.service_uri: service(proxy, headers, self.ytmusic)
            for service in standard_services
        }

        authenticated_services = [LastFM]

        [
            self.services.update(
                {
                    service.service_uri: service(
                        proxy,
                        headers,
                        self.ytmusic,
                        self.config["tubeify"][
                            f"{service.service_uri}_username"
                        ],
                        self.config["tubeify"][
                            f"{service.service_uri}_password"
                        ],
                    )
                }
            )
            for service in authenticated_services
        ]

        if self.tidal_playlists:
            self.services[Tidal.service_uri] = Tidal(
                proxy,
                {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 6.1) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/80.0.3987.149 Safari/537.36"
                    ),
                    "Accept": "*/*",
                },
                self.ytmusic,
            )

        # Amrap() is a generic client for AMRAP Radio Stations
        # see https://radiopages.info/ for a list of them
        self.services["3pbs"] = Amrap(
            proxy,
            headers,
            self.ytmusic,
            stationId="3pbs",
            stationName="3PBS 106.7FM",
            stationLogo="https://www.pbsfm.org.au/sites/default/files/pbs-logo-stacked-col-2014.gif",
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
            items = []
            # need to fix this
            if len(selected_services) > 1 and listoflists:
                logger.error(
                    f"listoflists only works for a single service, "
                    f"not {selected_services}"
                )

            for selected_service in selected_services:
                get_details_method = getattr(
                    self.backend.services[selected_service],
                    f"get_{kind}_details",
                    None,
                )

                if not listoflists:
                    listoflists = getattr(
                        self.backend,
                        f"{selected_service}_{kind}",
                        [],
                    )

                if listoflists:
                    items = get_details_method(listoflists)

                # need to fix this, too; listoflists reset to None
                # for each service in the list of selected services
                listoflists = None
                if items:
                    refs.extend(
                        [
                            Ref.directory(
                                uri=(
                                    f"tubeify:"
                                    f"{selected_service}:"
                                    f"{kind[:-1]}_"
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
                    uri=f"tubeify:{service.service_uri}:root",
                    name=service.service_name,
                )
                for service in self.backend.services.values()
            ]

            directoryrefs.extend(
                sorted(servicerefs, key=lambda x: x.name.lower())
            )

            return directoryrefs

        match = re.match(r"tubeify:(?P<service>.+):(?P<kind>.+)$", uri)
        if match:
            if match["service"] == "all":
                selected_services = self.backend.services.keys()
            else:
                selected_services = [match["service"]]

        if match and match["kind"] == "root":
            directoryrefs = []
            for selected_service in selected_services:
                directoryrefs.append(
                    Ref.directory(
                        uri=f"tubeify:{selected_service}:home",
                        name=f"{self.backend.services[selected_service].service_name} Homepage",
                    )
                )

                for list_type in ["users", "playlists"]:
                    if getattr(
                        self.backend,
                        f"{selected_service}_{list_type}",
                        None,
                    ):
                        directoryrefs.append(
                            Ref.directory(
                                uri=f"tubeify:{selected_service}:{list_type}",
                                name=f"{self.backend.services[selected_service].service_name} {list_type}",
                            )
                        )
            return directoryrefs

        elif match and match["kind"] == "home":
            playlistrefs = []
            for selected_service in selected_services:
                playlists = self.backend.services[
                    selected_service
                ].get_service_homepage()
                playlistrefs.extend(
                    [
                        Ref.directory(
                            uri=f"tubeify:{selected_service}:playlist_{playlist['id']}",
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
            playlists = self.backend.services[service].get_user_playlists(
                user_uri
            )
            playlistrefs = [
                Ref.directory(
                    uri=f"tubeify:{service}:playlist_{playlist['id']}",
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
            print(f"browse {service} playlist {playlist_uri}")
            # deal with things that are flagged as lists of lists
            # (eg, playlists or albums) not lists of tracks
            listoflists_match = re.match(
                r"^listoflists\-(?P<listoflists>.+)$", playlist_uri
            )
            if listoflists_match:
                return get_refs(
                    "playlists",
                    [service],
                    listoflists=[listoflists_match["listoflists"]],
                )

            tracks = self.backend.services[service].get_playlist_tracks(
                playlist_uri
            )
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

                # good_tracks.extend(
                #     [
                #         dict(
                #             video,
                #             **{
                #                 "videoId": video["videoDetails"]["videoId"],
                #                 "title": video["videoDetails"]["title"],
                #             },
                #         )
                #         for video in tracks
                #         if "videoDetails" in video
                #         and "videoId" in video["videoDetails"]
                #         and video["videoDetails"]["videoId"]
                #         and "title" in video["videoDetails"]
                #         and video["videoDetails"]["title"]
                #     ]
                # )

                good_albums = [
                    album
                    for album in tracks
                    if "type" in album
                    and album["type"] == "Album"
                    and album["browseId"]
                    and "title" in album
                    and album["title"]
                    and "artists" in album
                    and album["artists"]
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
                        f"{json.dumps([track for track in good_tracks if track is not None and len(track)>3])}"
                    ),
                    name=first_track["title"],
                )

            if good_albums:
                trackrefs.extend(
                    [
                        Ref.album(
                            uri=f"yt:playlist:{album['browseId']}",
                            name=f"{', '.join([artist['name'] for artist in album['artists']])}, '{album['title']}'",
                        )
                        for album in good_albums
                    ]
                )

            return trackrefs

        else:
            logger.warn(f"There was a problem with uri {uri}")

        return []

    def get_images(self, uris):
        images = {}
        for uri in uris:
            # service = uri.split(":")[1]
            # if (
            #     service in self.backend.services
            #     and self.backend.services[service].service_image
            # ):
            #     images[uri] = (
            #         Image(uri=self.backend.services[service].service_image),
            #     )
            service = uri.split(":")[1]
            if "playlist_" in uri:
                identifier = uri.split("playlist_")[1]
            else:
                identifier = None
            if service in self.backend.services:
                if identifier and self.backend.services[service].uri_images.get(
                    identifier
                ):
                    images[uri] = (
                        Image(
                            uri=self.backend.services[service].uri_images[
                                identifier
                            ]
                        ),
                    )
                elif self.backend.services[service].service_image:
                    images[uri] = (
                        Image(uri=self.backend.services[service].service_image),
                    )
        return images
