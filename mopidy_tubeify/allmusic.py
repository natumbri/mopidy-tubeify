import json
import re

from bs4 import BeautifulSoup as bs
from mopidy_youtube.comms import Client

from mopidy_tubeify import logger
from mopidy_tubeify.yt_matcher import search_and_get_best_match


class AllMusic(Client):

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 6.1) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/80.0.3987.149 Safari/537.36"
        )
    }

    def flatten(self, items):
        """Yield items from any nested list; see Reference."""
        for x in items:
            if isinstance(x, list) and not isinstance(x, (str, bytes)):
                for sub_x in self.flatten(x):
                    yield sub_x
            else:
                yield x

    def get_users_details(self, users):
        logger.warn(f"no Allmusic get_user_details, users: {users}")
        return []

    def get_user_playlists(self, user):
        logger.warn(f"no Allmusic get_user_playlists, user: {user}")
        return

    def get_playlists_details(self, playlists):
        def job(playlist):

            # for featured new releases
            match_FNR = re.match(r"^FNR\-(?P<albumId>.+)$", playlist)
            if match_FNR:
                playlist = match_FNR["albumId"]
                endpoint = f"https://www.allmusic.com/newreleases/{playlist}"
                data = self.session.get(endpoint, headers=self.headers)
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
        data = self.session.get(endpoint, headers=self.headers)
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

            # convert PT1H2M10S to 3730
            m = re.search(
                r"P((?P<weeks>\d+)W)?"
                + r"((?P<days>\d+)D)?"
                + r"T((?P<hours>\d+)H)?"
                + r"((?P<minutes>\d+)M)?"
                + r"((?P<seconds>\d+)S)?",
                track.get("duration", "0S"),
            )
            if m:
                val = (
                    int(m.group("weeks") or 0) * 604800
                    + int(m.group("days") or 0) * 86400
                    + int(m.group("hours") or 0) * 3600
                    + int(m.group("minutes") or 0) * 60
                    + int(m.group("seconds") or 0)
                )
            else:
                val = 0

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
        data = self.session.get(endpoint, headers=self.headers)
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