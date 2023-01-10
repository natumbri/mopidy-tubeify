import re

from bs4 import BeautifulSoup as bs

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import search_and_get_best_albums


class Discogs(ServiceClient):

    service_uri = "discogs"
    service_name = "Discogs"

    def get_playlist_tracks(self, playlist):
        # deal with what to listen to pages
        match_WTLT = re.match(r"^WTLT\-(?P<wtltpage>.+)$", playlist)
        if match_WTLT:
            logger.debug(f'matched "what to listen to page:" {playlist}')
            playlist = match_WTLT["wtltpage"]
            endpoint = f"https://www.discogs.com/digs/music/{playlist}"
            data = self.session.get(endpoint)
            soup = bs(data.text, "html5lib")
            new_releases_filter = soup.find_all(
                "div", class_=re.compile(r".*release-item.*")
            )

            albums = [
                (
                    new_release.find(
                        "div",
                        class_=re.compile(r".*release(?:-block)?-artist.*"),
                    )
                    .text.strip()
                    .split(" / "),
                    new_release.find(
                        "div",
                        class_=re.compile(r".*release(?:-block)?-title.*"),
                    ).text.strip(),
                )
                for new_release in new_releases_filter
            ]

            albums_to_return = search_and_get_best_albums(
                [album for album in albums if album[1]], self.ytmusic
            )

            return list(flatten(albums_to_return))

        # deal with other things
        return

    def get_service_homepage(self):

        endpoint = r"https://www.discogs.com/digs/music/"
        data = self.session.get(endpoint)
        soup = bs(data.text, "html5lib")
        if_you_like_divs = soup.find_all(
            "li", attrs={"class": re.compile(".*tag-if-you-like.*")}
        )

        if_you_like_dicts = [
            {"title": div.h3.a.text, "href": div.h3.a["href"]}
            for div in if_you_like_divs
        ]

        if_you_like_results = [
            {
                "name": f"{if_you_like_dict['title']}",
                "id": f"WTLT-{if_you_like_dict['href'][31:]}",
            }
            for if_you_like_dict in if_you_like_dicts
        ]

        of_all_time_divs = soup.find_all(
            "li", attrs={"class": re.compile(".*category-music.*")}
        )
        of_all_time_divs[:] = [
            of_all_time_div
            for of_all_time_div in of_all_time_divs
            if re.match(".*of All Time$", of_all_time_div.text.strip())
        ]

        of_all_time_dicts = [
            {"title": div.text.strip(), "href": div.a["href"]}
            for div in of_all_time_divs
        ]

        of_all_time_results = [
            {
                "name": f"{of_all_time_dict['title']}",
                "id": f"WTLT-{of_all_time_dict['href'][31:]}",
            }
            for of_all_time_dict in of_all_time_dicts
        ]

        return if_you_like_results + of_all_time_results
