import re

from bs4 import BeautifulSoup as bs
from mopidy_youtube.data import extract_video_id as extract_yt_video_id

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
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

                card_regex = re.compile("^card( .+)?$")
                cards_soup = soup.find_all("div", class_=card_regex)

                # only bother with cards with View playlist button
                cards_soup[:] = [
                    card
                    for card in cards_soup
                    if card.find(text="View playlist")
                ]

                playlist_results = []
                for card in cards_soup:
                    playlist_results.append(
                        {
                            "name": card.find(class_="card__anchor").text,
                            "id": card.find(class_="card__anchor").get("href"),
                        }
                    )
                return playlist_results
            else:
                # for other sorts of tripler playlists
                pass

        results = []

        # does tripler uses a captcha? be careful before going multi-threaded
        [results.append(job(playlist)) for playlist in playlists]

        return list(flatten(results))

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

        endpoint = "https://www.rrr.org.au/explore/programs"
        data = self.session.get(endpoint)
        soup = bs(data.text, "html5lib")

        card_regex = re.compile("^card( .+)?$")
        cards_soup = soup.find_all("div", class_=card_regex)

        program_regex = re.compile(r"^/explore/programs/(?P<programId>.+)$")
        track_dicts = []

        [
            track_dicts.append(
                {
                    "name": card.find(class_="card__text").a.text,
                    "id": f"listoflists-PROGRAM-{program_regex.match((card.find(class_='card__text').a.get('href')))['programId']}",
                }
            )
            for card in cards_soup
        ]

        return track_dicts
