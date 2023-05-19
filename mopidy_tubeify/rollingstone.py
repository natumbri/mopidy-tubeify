import json
import re
from html import unescape

from bs4 import BeautifulSoup as bs
from unidecode import unidecode

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import (
    search_and_get_best_albums,
    search_and_get_best_match,
)


class RollingStone(ServiceClient):
    service_uri = "rollingstone"
    service_name = "Rolling Stone Magazine"

    def get_playlists_details(self, playlists):
        # is this really a list of playlists, or is it a special case?
        if len(playlists) == 1:
            # did we get here from the homepage?
            if playlists[0] == "RS500BSOAT":
                endpoint = r"https://www.rollingstone.com/music/music-lists/best-songs-of-all-time-1224767/"
                idPrefix = playlists[0][5:]
            elif playlists[0] == "RS500BAOAT":
                endpoint = r"https://www.rollingstone.com/music/music-lists/best-albums-of-all-time-1062063/"
                idPrefix = playlists[0][5:]  # "listoflists-" + playlists[0][5:]
            elif playlists[0] == "RS100BDAOAT":
                endpoint = r"https://www.rollingstone.com/music/music-lists/100-best-debut-albums-of-all-time-143608/"
                idPrefix = playlists[0][5:]  # "listoflists-" + playlists[0][5:]
            elif playlists[0] == "RS100GCAOAT":
                endpoint = r"https://www.rollingstone.com/music/music-lists/best-country-albums-1234581876/"
                idPrefix = playlists[0][5:]  # "listoflists-" + playlists[0][5:]

            segments_json = self._get_RS_json(endpoint)["listNavBar"][
                "generatedRanges"
            ]["800"]
            segment_dicts = [
                {
                    "name": f'{segment["positionDisplayStart"]} - {segment["positionDisplayEnd"]}',
                    "id": f"{idPrefix}-"
                    + endpoint
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
        # is this a segment from xAOAT?
        match_xAOAT = re.match(r"^[A-Z]{1,2}AOAT\-(?P<segment>.+)$", playlist)
        if match_xAOAT:
            albums_json = self._get_RS_json(match_xAOAT["segment"])["gallery"]
            name_artists = [
                re.match(
                    r"^(?P<artist>.+),\s'(?P<name>.+)'(\s\((?P<year>\d{4})\))?$",
                    album["title"],
                )
                for album in albums_json
            ]

            # works for 100 greatest country albums where "title" is just the artist
            # and "additionalDescription" is the name of the album
            if not [album for album in name_artists if album]:
                name_artists = [
                    {
                        "artist": album["title"],
                        "name": album["additionalDescription"].replace("'", ""),
                    }
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

            return ytalbums

        # is this a segment of BSOAT?
        match_BSOAT = re.match(r"^BSOAT\-(?P<segment>.+)$", playlist)
        if match_BSOAT:
            tracks_json = self._get_RS_json(match_BSOAT["segment"])["gallery"]
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
        # future: programatically generate album and song lists from the
        # RS lists page (https://www.rollingstone.com/music/music-lists/)
        # to include in the library.  The "id" would ideally be something
        # like f"listoflists-{url of first page of the list}"

        # now: hard code a few lists
        return [
            {
                "name": "Rolling Stone 500 Best Songs of All Time",
                "id": "listoflists-RS500BSOAT",
            },
            {
                "name": "Rolling Stone 500 Best Albums of All Time",
                "id": "listoflists-RS500BAOAT",
            },
            {
                "name": "Rolling Stone 100 Best Debut Albums of All Time",
                "id": "listoflists-RS100BDAOAT",
            },
            {
                "name": "Rolling Stone 100 Greatest Country Albums of All Time",
                "id": "listoflists-RS100GCAOAT",
            },
        ]

    def _get_RS_json(self, endpoint):
        logger.info(endpoint)
        data = self.session.get(endpoint + "/", allow_redirects=False)
        soup = bs(data.text, "html5lib")
        json_script = soup.find("script", id="pmc-lists-front-js-extra")
        script_text = unidecode(json_script.contents[0])
        json_re = re.compile(r"var\ pmcGalleryExports\ \=\ (?P<json_var>.+);")

        return json.loads(
            unescape(json_re.search(script_text)["json_var"])
            .replace("‘", "'")
            .replace("’", "'")
            # unescape(json_re.search(unidecode(script_text))["json_var"])
            # .replace("‘", "'")
            # .replace("’", "'")
        )
