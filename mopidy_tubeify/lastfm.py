import re
from mopidy_tubeify.serviceclient import ServiceClient
import pylast
from pylast import Album, LovedTrack, PlayedTrack, TopItem, Track
from mopidy_tubeify.data import flatten
from mopidy_tubeify.yt_matcher import (
    search_and_get_best_albums,
    search_and_get_best_match,
)

from mopidy_tubeify import logger
from mopidy_scrobbler.frontend import API_KEY, API_SECRET, PYLAST_ERRORS


class Lastfm(ServiceClient):
    service_uri = "lastfm"
    service_name = "Last.fm"

    playlist_kinds = {
        "get_loved_tracks": {"name": "loved tracks", "params": {"limit": 20}},
        # "get_now_playing":{},
        "get_recent_tracks": {
            "name": "recent tracks",
            "params": {"limit": 20},
        },
        # "get_tagged_albums":{"limit":20},
        # "get_tagged_artists":{"limit":20},
        # "get_tagged_tracks":{"limit":20},
        "get_top_albums": {
            "name": "top albums this month",
            "params": {"limit": 20, "period": "PERIOD_1MONTH"},
        },
        "get_top_artists": {
            "name": "top artists this month",
            "params": {"limit": 20, "period": "PERIOD_1MONTH"},
        },
        # "get_top_tags": {"name": "top tags", "params": {"limit": 20}},
        "get_top_tracks": {
            "name": "top tracks this month",
            "params": {"limit": 20, "period": "PERIOD_1MONTH"},
        },
    }

    def __init__(self, proxy, headers, ytm_client, username, password):
        super().__init__(proxy, headers, ytm_client)
        self.username = username
        self.password = password

        try:
            self.lastfm = pylast.LastFMNetwork(
                api_key=API_KEY,
                api_secret=API_SECRET,
                username=self.username,
                password_hash=pylast.md5(self.password),
            )
            logger.info("Tubeify connected to Last.fm")
        except PYLAST_ERRORS as exc:
            logger.error(f"Error during Last.fm setup: {exc}")
            self.stop()

    def get_users_details(self, users):
        results = [
            {"id": user, "name": user}
            for user in ([self.username] + list(users))
        ]
        return results

    def get_user_playlists(self, user):
        return [
            {
                "name": f"{user} {self.playlist_kinds[playlist]['name']}",
                "id": f"{playlist}:{user}",
            }
            for playlist in self.playlist_kinds
        ]

    def get_playlist_tracks(self, playlist):
        match = re.match(r"^(?P<kind>.+):(?P<user>.+)$", playlist)

        user_object = self.lastfm.get_user(match["user"])

        get_pylast_object_method = getattr(
            user_object,
            match["kind"],
            None,
        )

        pylast_object = get_pylast_object_method(
            **self.playlist_kinds[match["kind"]]["params"]
        )

        scrobbled_items = []
        for scrobbled_item in pylast_object:
            if type(scrobbled_item) == TopItem:
                scrobbled_items.append(scrobbled_item.item)
            elif type(scrobbled_item) in [PlayedTrack, LovedTrack]:
                scrobbled_items.append(scrobbled_item.track)

        tracks = [
            {
                "song_name": scrobbled_item.title,
                "song_artists": [scrobbled_item.artist.get_name()],
                "song_duration": 0,
                "isrc": None,
            }
            for scrobbled_item in scrobbled_items
            if type(scrobbled_item) == Track
        ]

        logger.debug(
            f"total tracks for {match['user']}, {match['kind']}: {len(tracks)}"
        )

        matched_tracks = search_and_get_best_match(tracks, self.ytmusic)

        albums = [
            (
                [scrobbled_item.artist.get_name()],
                scrobbled_item.title,
            )
            for scrobbled_item in scrobbled_items
            if type(scrobbled_item) == Album
        ]

        logger.debug(
            f"total albums for {match['user']}, {match['kind']}: {len(albums)}"
        )

        albums_to_return = search_and_get_best_albums(
            [album for album in albums if album[1]], self.ytmusic
        )

        matched_albums = list(flatten(albums_to_return))

        return matched_tracks + matched_albums

    def get_service_homepage(self):
        logger.warn("no service homepage, get_service_homepage")
        return
