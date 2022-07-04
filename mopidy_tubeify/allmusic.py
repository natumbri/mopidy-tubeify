import json
import re

from bs4 import BeautifulSoup as bs
from mopidy_youtube.timeformat import ISO8601_to_seconds

from mopidy_tubeify import logger
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import search_and_get_best_match


class AllMusic(ServiceClient):
    def get_playlists_details(self, playlists):
        def job(playlist):

            # for featured new releases
            match_FNR = re.match(r"^FNR\-(?P<albumId>.+)$", playlist)
            if match_FNR:
                logger.debug(f'matched "featured new release" {playlist}')
                playlist = match_FNR["albumId"]
                endpoint = f"https://www.allmusic.com/newreleases/{playlist}"
                data = self.session.get(endpoint)
                soup = bs(data.text, "html5lib")
                albumId_re = re.compile(r"^.+/album/(?P<albumId>.+)$")
                new_releases_filter = soup.find_all("div", class_="new-release")
                playlist_results = []
                for new_release in new_releases_filter:
                    playlist_results.append(
                        {
                            "name": f"{new_release.find('div', class_='artist').text.strip()}, \"{new_release.find('div', class_='title').text.strip()}\"",
                            "id": albumId_re.match(
                                new_release.find("div", class_="title").a[
                                    "href"
                                ]
                            )["albumId"],
                        }
                    )
                return playlist_results
            else:
                # for other sorts of allmusic playlists
                pass

        results = []

        # does allmusic uses a captcha? be careful before going multi-threaded
        [results.append(job(playlist)) for playlist in playlists]

        return list(self.flatten(results))

    def get_playlist_tracks(self, playlist):

        # deal with featured new releases pages
        if re.match(r"^FNR\-(?P<albumId>.+)$", playlist):
            return self.get_playlists_details([playlist])

        endpoint = f"https://www.allmusic.com/album/{playlist}"
        data = self.session.get(endpoint)
        soup = bs(data.text, "html5lib")
        tracks = []
        json_script = soup.find("script", {"type": "application/ld+json"})
        json_data = json.loads(json_script.text)

        # if the album is a re-release, get_playlist_tracks from the original
        if re.match(r"^.+/release/.+$", json_data["url"]):
            return self.get_playlist_tracks(
                re.match(
                    r"^.+/album/(?P<albumId>.+)$", json_data["releaseOf"]["url"]
                )["albumId"]
            )

        for track in json_data["tracks"]:

            # convert ISO8601 (PT1H2M10S) to s (3730)
            val = ISO8601_to_seconds(track.get("duration", "0S"))

            track_dict = {
                "song_name": track["name"],
                "song_artists": [
                    artist["name"] for artist in json_data["byArtist"]
                ],
                "song_duration": val,
                "isrc": None,
            }

            tracks.append(track_dict)

        return search_and_get_best_match(tracks, self.ytmusic)

    def get_service_homepage(self):

        endpoint = r"https://www.allmusic.com/newreleases"
        data = self.session.get(endpoint)
        soup = bs(data.text, "html5lib")

        week_filter = soup.find("select", {"name": "week-filter"})
        weeks = week_filter.find_all("option")

        track_dicts = []

        for week in weeks:
            track_dicts.append(
                {
                    "name": f"Featured New Releases, {week.text.strip()}",
                    "id": f"listoflists-FNR-{week['value']}",
                }
            )

        return track_dicts
