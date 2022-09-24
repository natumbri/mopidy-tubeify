import json
import re
from html import unescape

from bs4 import BeautifulSoup as bs
from mopidy_youtube.timeformat import ISO8601_to_seconds

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import (
    search_and_get_best_album,
    search_and_get_best_match,
)


class AllMusic(ServiceClient):
    def get_playlists_details(self, playlists):
        def job(playlist):

            # for featured new releases
            match_FNR = re.match(r"^FNR\-(?P<FNRdate>.+)$", playlist)
            if match_FNR:
                logger.debug(f'matched "featured new release" {playlist}')
                playlist = match_FNR["FNRdate"]
                endpoint = f"https://www.allmusic.com/newreleases/{playlist}"
                data = self.session.get(endpoint)
                soup = bs(data.text, "html5lib")
                albumId_re = re.compile(r"^.+/album/(?P<albumId>.+)$")
                new_releases_filter = soup.find_all("div", class_="new-release")
                return [
                    {
                        "name": (
                            f"{new_release.find('div', class_='artist').text.strip()}, "
                            f"\"{new_release.find('div', class_='title').text.strip()}\""
                        ),
                        "id": albumId_re.match(
                            new_release.find("div", class_="title").a["href"]
                        )["albumId"],
                    }
                    for new_release in new_releases_filter
                ]
            else:
                # for other sorts of allmusic playlists
                pass

        results = []

        # does allmusic uses a captcha? be careful before going multi-threaded
        [results.append(job(playlist)) for playlist in playlists]

        return list(flatten(results))

    def get_playlist_tracks(self, playlist):

        # deal with featured new releases pages
        if re.match(r"^FNR\-(?P<albumId>.+)$", playlist):
            return self.get_playlists_details([playlist])

        endpoint = f"https://www.allmusic.com/album/{playlist}"
        data = self.session.get(endpoint)
        soup = bs(data.text, "html5lib")
        json_script = soup.find("script", {"type": "application/ld+json"})
        json_data = json.loads(json_script.text)

        if "byArtist" in json_data:
            artists = [
                unescape(artist["name"]) for artist in json_data["byArtist"]
            ]
        elif "releaseOf" in json_data and "byArtist" in json_data["releaseOf"]:
            artists = [
                unescape(artist["name"])
                for artist in json_data["releaseOf"]["byArtist"]
            ]
        else:
            artists = ["Unknown"]

        title = f"{unescape(json_data['name'])}"
        artists_albumtitle = (artists, title)

        try:
            # experimental, using ytmusic album instead of track-by-track matching
            album_browseId_list = search_and_get_best_album(
                artists_albumtitle, self.ytmusic
            )
            album_browseId = album_browseId_list[0]["browseId"]
            album = self.ytmusic.get_album(album_browseId)
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
                            "id": album_browseId,
                        }
                    }
                )
                for track in tracks
            ]
            return tracks

        except Exception as e:

            if re.match(r"^.+/release/.+$", json_data["url"]):
                logger.warning(
                    f"album {album['title']} is a re-release; getting playlist_tracks from the original"
                )
                return self.get_playlist_tracks(
                    re.match(
                        r"^.+/album/(?P<albumId>.+)$",
                        json_data["releaseOf"]["url"],
                    )["albumId"]
                )

            logger.warn(
                f"error {e} getting album {artists_albumtitle} "
                f"from ytmusic; trying individual tracks"
            )

            tracks = [
                {
                    "song_name": track["name"],
                    "song_artists": [
                        artist["name"] for artist in json_data["byArtist"]
                    ],
                    "song_duration": ISO8601_to_seconds(
                        track.get("duration", "0S")
                    ),
                    "isrc": None,
                }
                for track in json_data["tracks"]
            ]

            return search_and_get_best_match(tracks, self.ytmusic)

    def get_service_homepage(self):

        endpoint = r"https://www.allmusic.com/newreleases"
        data = self.session.get(endpoint)
        soup = bs(data.text, "html5lib")

        week_filter = soup.find("select", {"name": "week-filter"})
        weeks = week_filter.find_all("option")

        return [
            {
                "name": f"Featured New Releases, {week.text.strip()}",
                "id": f"listoflists-FNR-{week['value']}",
            }
            for week in weeks
        ]
