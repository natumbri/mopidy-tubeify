import json
import re

from bs4 import BeautifulSoup as bs

from mopidy_tubeify import logger
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import (
    search_and_get_best_album
)


class Pitchfork(ServiceClient):
    def get_playlists_details(self, playlists):
        def job(playlist):

            # for recently reviewed albums
            match_RRA = re.match(r"^RRA\-(?P<reviewPage>.+)$", playlist)
            if match_RRA:
                logger.debug(f'matched "recently reviewed albums" {playlist}')
                reviewPage = match_RRA["reviewPage"]
                endpoint = f"https://pitchfork.com/reviews/albums/?{reviewPage}"
                data = self.session.get(endpoint)
                soup = bs(data.text, "html5lib")
                script_re = re.compile(r"^window.App=(?P<json_data>.*);$")
                json_script = soup.find("script", string=script_re)
                json_data = json.loads(
                    script_re.match(json_script.text)["json_data"]
                )["context"]["dispatcher"]["stores"]["ReviewsStore"]["items"]
                item_list = [
                    json_data[item]["tombstone"]["albums"][0]["album"]
                    for item in json_data
                ]

                playlist_results = []

                for item in item_list:
                    album = f"{item['artists'][0]['display_name']}, '{item['display_name']}'"

                    playlist_results.append(
                        {
                            "name": album,
                            "id": search_and_get_best_album(
                                album, self.ytmusic
                            )[0]["browseId"],
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

        # deal with recently reviewed albums pages
        if re.match(r"^RRA\-(?P<albumId>.+)$", playlist):
            return self.get_playlists_details([playlist])

        album = self.ytmusic.get_album(playlist)

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
                        "id": playlist,
                    }
                }
            )
            for track in tracks
        ]

        return tracks

    def get_service_homepage(self):

        track_dicts = []

        track_dicts.append(
            {
                "name": r"12 Recently Reviewed Albums",
                "id": r"listoflists-RRA-page=1",
            }
        )

        track_dicts.append(
            {
                "name": r"12 Previously Reviewed Albums",
                "id": r"listoflists-RRA-page=2",
            }
        )

        track_dicts.append(
            {
                "name": r"12 Albums reviewed a while ago",
                "id": r"listoflists-RRA-page=3",
            }
        )

        return track_dicts
