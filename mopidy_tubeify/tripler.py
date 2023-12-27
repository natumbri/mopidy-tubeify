import re

from bs4 import BeautifulSoup as bs
from mopidy_youtube.data import extract_video_id as extract_yt_video_id

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import search_and_get_best_match


class TripleR(ServiceClient):
    service_uri = "tripler"
    service_name = "3RRR 102.7FM"
    service_image = "https://cdn-images-w3.rrr.org.au/1V_nPrxhwEWsjq5M5vV82UmmKwo=/600x600/filters:quality(85)/https://s3.ap-southeast-2.amazonaws.com/assets-w3.rrr.org.au/assets/091/a3b/6b5/091a3b6b51ac36547024c135434b0dacafd174d4/RRR-Facebook-Logo-White-Backg.jpg"
    service_endpoint = "https://www.rrr.org.au"

    def get_playlists_details(self, playlists):
        def job(playlist):
            # deal with program pages
            match_PROGRAM = re.match(r"^PROGRAM\-(?P<programId>.+)$", playlist)
            if match_PROGRAM:
                logger.debug(f'matched "program" {playlist}')
                programId = match_PROGRAM["programId"]
                endpoint = f"{self.service_endpoint}/explore/programs/{programId}/episodes/page?page=1"
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

        endpoint = f"{self.service_endpoint}{playlist}"
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
        endpoint = f"{self.service_endpoint}/explore/programs"
        data = self.session.get(endpoint)
        soup = bs(data.text, "html5lib")

        card_regex = re.compile("^card( .+)?$")
        cards_soup = soup.find_all("div", class_=card_regex)

        program_regex = re.compile(r"^/explore/programs/(?P<programId>.+)$")
        track_dicts = []

        for card in cards_soup:
            name = card.find(class_="card__text").a.text
            program_id = f"listoflists-PROGRAM-{program_regex.match((card.find(class_='card__text').a.get('href')))['programId']}"
            image = card.find("img")["data-src"]
            track_dicts.append({"name": name, "id": program_id})
            self.uri_images[program_id] = image

        return track_dicts
