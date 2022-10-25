import json
import re
from html import unescape

from bs4 import BeautifulSoup as bs
from mopidy_youtube.data import extract_playlist_id

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten

from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import (
    search_and_get_best_albums,
    search_and_get_best_match,
)


class RollingStone(ServiceClient):
    def get_playlists_details(self, playlists):

        # is this really a list of playlists, or is it a special case?
        if len(playlists) == 1:

            # is this a segment from BAOAT?
            match_BAOAT = re.match(r"^BAOAT\-(?P<segment>.+)$", playlists[0])
            if match_BAOAT:
                endpoint = r"https://www.rollingstone.com/music/music-lists/best-albums-of-all-time-1062063/"
                data = self.session.get(
                    endpoint + match_BAOAT["segment"] + "/",
                    allow_redirects=False,
                )
                soup = bs(data.text, "html5lib")
                json_script = soup.find("script", id="pmc-lists-front-js-extra")
                json_re = re.compile(
                    r"var\ pmcGalleryExports\ \=\ (?P<json_var>.+);"
                )
                albums_json = json.loads(
                    unescape(json_re.search(json_script.text)["json_var"])
                    .replace("‘", "'")
                    .replace("’", "'")
                )["gallery"]
                name_artists = [
                    re.match(
                        r"^(?P<artist>.+),\s'(?P<name>.+)'$", album["title"]
                    )
                    for album in albums_json
                ]
                albums = [
                    (
                        album["artist"].split(","),
                        album["name"],
                    )
                    for album in name_artists
                    if album
                ]
                ytalbums = list(
                    flatten(search_and_get_best_albums(albums, self.ytmusic))
                )
                return [
                    {
                        "name": ytalbum["title"],
                        "id": f"yt:playlist:{ytalbum['browseId']}",
                    }
                    for ytalbum in ytalbums
                ]

            # did we get here from the homepage?
            if playlists[0] == "RS500BSOAT":
                endpoint = r"https://www.rollingstone.com/music/music-lists/best-songs-of-all-time-1224767/"
                idPrefix = playlists[0][5:]
            elif playlists[0] == "RS500BAOAT":
                endpoint = r"https://www.rollingstone.com/music/music-lists/best-albums-of-all-time-1062063/"
                idPrefix = "listoflists-" + playlists[0][5:]
            data = self.session.get(endpoint)
            soup = bs(data.text, "html5lib")
            json_script = soup.find("script", id="pmc-lists-front-js-extra")
            json_re = re.compile(
                r"var\ pmcGalleryExports\ \=\ (?P<json_var>.+);"
            )
            segments_json = json.loads(
                json_re.search(json_script.text)["json_var"]
            )["listNavBar"]["generatedRanges"]["800"]
            segment_dicts = [
                {
                    "name": f'{segment["positionDisplayStart"]} - {segment["positionDisplayEnd"]}',
                    "id": f"{idPrefix}-"
                    + re.match(f"^{endpoint}(?P<tail>.+)$", segment["link"])[
                        "tail"
                    ],
                }
                for segment in segments_json
            ]

            return segment_dicts

        # ordinary case of list of playlists here

        logger.warn("RollingStone get_playlists_details not returning anything")
        return

    def get_playlist_tracks(self, playlist):

        # is this an ytmalbum (with a browseId) from a segment of BAOAT?
        ytmalbum = extract_playlist_id(playlist)
        if ytmalbum:
            album = self.ytmusic.get_album(ytmalbum)
            tracks = album["tracks"]
            fields = ["artists", "thumbnails"]

            [
                track.update({field: album[field]})
                for field in fields
                for track in tracks
                if track[field] is None
            ]

            [
                track.update(
                    {
                        "album": {
                            "name": album["title"],
                            "id": ytmalbum,
                        }
                    }
                )
                for track in tracks
            ]
            return tracks

        # is this a segment of BAOAT?
        match_BAOAT = re.match(r"^BAOAT\-(?P<segment>.+)$", playlist)
        if match_BAOAT:
            return self.get_playlists_details([playlist])

        # is this a segment of BSOAT?
        match_BSOAT = re.match(r"^BSOAT\-(?P<segment>.+)$", playlist)
        if match_BSOAT:
            endpoint = r"https://www.rollingstone.com/music/music-lists/best-songs-of-all-time-1224767/"
            data = self.session.get(
                endpoint + match_BSOAT["segment"] + "/", allow_redirects=False
            )
            soup = bs(data.text, "html5lib")
            json_script = soup.find("script", id="pmc-lists-front-js-extra")
            json_re = re.compile(
                r"var\ pmcGalleryExports\ \=\ (?P<json_var>.+);"
            )

            tracks_json = json.loads(
                unescape(json_re.search(json_script.text)["json_var"])
                .replace("‘", "'")
                .replace("’", "'")
            )["gallery"]

            name_artists = [
                re.match(r"^(?P<artist>.+),\s'(?P<name>.+)'$", track["title"])
                for track in tracks_json
            ]

            tracks = [
                {
                    "song_name": track["name"],
                    "song_artists": track["artist"].split(","),
                    "song_duration": 0,
                    "isrc": None,
                }
                for track in name_artists
                if track
            ]

            return search_and_get_best_match(tracks, self.ytmusic)

    def get_service_homepage(self):
        return [
            {
                "name": "Rolling Stone 500 Best Songs of All Time",
                "id": "listoflists-RS500BSOAT",
            },
            {
                "name": "Rolling Stone 500 Best Albums of All Time",
                "id": "listoflists-RS500BAOAT",
            },
        ]
