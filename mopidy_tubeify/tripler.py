import re

from bs4 import BeautifulSoup as bs
from mopidy_youtube.data import extract_video_id as extract_yt_video_id

from mopidy_tubeify import logger
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import search_and_get_best_match


class TripleR(ServiceClient):
    def get_users_details(self, users):
        logger.warn(f"no details, get_users_details: {users}")
        return []

    def get_user_playlists(self, user):
        logger.warn(f"no playlists, get_user_playlists: {user}")
        return

    def get_playlists_details(self, playlists):
        def job(playlist):

            # deal with program pages
            match_PROGRAM = re.match(r"^PROGRAM\-(?P<programId>.+)$", playlist)
            if match_PROGRAM:
                logger.debug(f'matched "program" {playlist}')
                programId = match_PROGRAM["programId"]
                endpoint = f"https://www.rrr.org.au/explore/programs/{programId}/episodes/page?page=1"
                data = self.session.get(endpoint)
                soup = bs(data.content.decode("utf-8"), "html5lib")
                cards_soup = soup.find_all("a", class_="card__anchor")
                playlist_results = []
                for card in cards_soup:
                    playlist_results.append(
                        {
                            "name": card.text,
                            "id": card["href"],
                        }
                    )
                return playlist_results
            else:
                # for other sorts of tripler playlists
                pass

        results = []

        # does tripler uses a captcha? be careful before going multi-threaded
        [results.append(job(playlist)) for playlist in playlists]

        return list(self.flatten(results))

    def get_playlist_tracks(self, playlist):

        # deal with program pages
        if re.match(r"^PROGRAM\-(?P<programId>.+)$", playlist):
            return self.get_playlists_details([playlist])

        endpoint = f"https://www.rrr.org.au{playlist}"
        data = self.session.get(endpoint)
        soup = bs(data.text, "html5lib")

        tracks_soup = soup.find_all(
            "li", class_="audio-summary__track clearfix"
        )

        tracks = [
            {
                "song_name": track_soup.find(
                    class_="audio-summary__track-title"
                ).text,
                "song_artists": [
                    track_soup.find(class_="audio-summary__track-artist").text
                ],
                "song_duration": 0,
                "isrc": None,
                "videoId": extract_yt_video_id(
                    track_soup.find(class_="audio-summary__track-title").get(
                        "href"
                    )
                ),
            }
            for track_soup in tracks_soup
        ]

        return search_and_get_best_match(tracks, self.ytmusic)

    def get_service_homepage(self):

        track_dicts = []

        track_dicts.append(
            {
                "name": r"Off The Record",
                "id": r"listoflists-PROGRAM-off-the-record",
            }
        )

        track_dicts.append(
            {
                "name": r"Maps",
                "id": r"listoflists-PROGRAM-maps",
            }
        )

        return track_dicts
