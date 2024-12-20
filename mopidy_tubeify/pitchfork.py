import json
import re
from unidecode import unidecode
from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import (
    search_and_get_best_albums,
    search_and_get_best_match,
)


class Pitchfork(ServiceClient):
    service_uri = "pitchfork"
    service_name = "Pitchfork"
    service_image = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/df/Pitchfork_logo_symbol.svg/480px-Pitchfork_logo_symbol.svg.png"
    service_endpoint = "https://pitchfork.com"

    service_schema = {
        "reviewed_albums": {
            "item": {
                "name": "script",
                "string": re.compile(
                    r"window\.__PRELOADED_STATE__\ \=\ (?P<json_data>.*)\;"
                ),
            },
        },
        "listed_items": {
            "item": {
                "name": "h2",
                # "text": re.compile(r".*\:\ .*")  # why can't I use "text" here?
            }
        },
        "lists": {
            "container": {
                "name": "div",
                "attrs": {"data-testid": "SummaryRiverWrapper"},
            },
            "item": {
                "name": "a",
                "attrs": {"class": re.compile(r"summary-item__hed-link")},
            },
        },
    }

    listtypes = [
        ("Readers", re.compile(r".*According to Pitchfork Readers")),
        (
            "Albums",
            re.compile(r"Best\ .*Albums"),
        ),  # "Great Records" "Favourite Albums" "Anticipated Albums"
        ("Tracks", re.compile(r"Best\ .*Songs")),  # "Best Tracks" "Best Music"
    ]

    def get_playlists_details(self, playlists):
        match_LAG = re.match(r"^LAG\-(?P<ListAndGuidePage>.+)$", playlists[0])
        if match_LAG:
            logger.debug(f'matched "lists and guides page" {playlists[0]}')
            lists = self._get_items_soup(
                f'/{match_LAG["ListAndGuidePage"]}', "lists"
            )
            list_dicts = []

            def job(listitem):
                if firstlisttype := next(
                    (
                        listtype[0]
                        for listtype in self.listtypes
                        if listtype[1].search(listitem.text)
                    ),
                    None,
                ):
                    return [
                        {
                            "name": listitem.text,
                            "id": f"{firstlisttype}-{listitem.get('href')}",
                        }
                    ]

                return []

            for listitem in map(job, lists):
                list_dicts.extend(listitem)

            return list_dicts

    def get_playlist_tracks(self, playlist):
        # deal with album review pages
        match_ARP = re.match(r"^ARP\-(?P<reviewPage>.+)$", playlist)
        if match_ARP:
            logger.debug(f'matched "album review page" {playlist}')
            return self._Album_Review_Page(match_ARP["reviewPage"])

        # deal with lists and guides pages
        if re.match(r"^LAG\-(?P<albumId>.+)$", playlist):
            return self.get_playlists_details([playlist])

        # deal with albums pages
        match_Albums = re.match(r"^Albums\-(?P<albumsPage>.+)$", playlist)
        if match_Albums:
            logger.info(f'matched "albums page" {playlist}')
            albums = [
                (item.text.split(":")[0].split("/"), item.text.split(":")[1])
                for item in self._get_items_soup(
                    f'/{match_Albums["albumsPage"]}', "listed_items"
                )
                if re.search(r".*\:\ .*", item.text)
            ]

            albums_to_return = search_and_get_best_albums(
                [album for album in albums if album[1]], self.ytmusic
            )
            return list(flatten(albums_to_return))

        # deal with tracks pages
        match_Tracks = re.match(r"^Tracks\-(?P<tracksPage>.+)$", playlist)
        if match_Tracks:
            logger.debug(f'matched "tracks page" {playlist}')
            tracks = [
                {
                    "song_name": unidecode(item.text.split(":")[1])
                    .replace('"', "")
                    .strip(),
                    "song_artists": item.text.split(":")[0].split("/"),
                    "isrc": None,
                }
                for item in self._get_items_soup(
                    f'/{match_Tracks["tracksPage"]}', "listed_items"
                )
                if re.search(r".*\:\ .*", item.text)
            ]
            return search_and_get_best_match(tracks, self.ytmusic)

    def get_service_homepage(self):
        track_dicts = []

        track_dicts.append(
            {
                "name": r"Best New Albums",
                # "id": r"listoflists-ARP-reviews/best/albums/?page=1",
                "id": r"ARP-reviews/best/albums/?page=1",
            }
        )

        track_dicts.append(
            {
                "name": r"Best New Reissues",
                "id": r"ARP-reviews/best/reissues/?page=1",
            }
        )

        track_dicts.append(
            {
                "name": r"8.0+ Reviews",
                "id": r"ARP-reviews/best/high-scoring-albums/?page=1",
            }
        )

        track_dicts.append(
            {
                "name": r"Sunday Reviews",
                "id": r"ARP-reviews/sunday/?page=1",
            }
        )

        track_dicts.append(
            {
                "name": r"12 Recently Reviewed Albums",
                "id": r"ARP-reviews/albums/?page=1",
            }
        )

        track_dicts.append(
            {
                "name": r"12 Previously Reviewed Albums",
                "id": r"ARP-reviews/albums/?page=2",
            }
        )

        track_dicts.append(
            {
                "name": r"12 Albums reviewed a while ago",
                "id": r"ARP-reviews/albums/?page=3",
            }
        )

        track_dicts.append(
            {
                "name": r"Lists and Guides",
                "id": r"listoflists-LAG-features/lists-and-guides",
            }
        )

        return track_dicts

    def _Album_Review_Page(self, review_page_url):
        json_item = str(
            self._get_items_soup(f"/{review_page_url}", "reviewed_albums")[
                0
            ].contents
        )

        json_script = self.service_schema["reviewed_albums"]["item"][
            "string"
        ].search(json_item)

        json_data = json.loads(
            (json_script["json_data"]).encode().decode("unicode-escape")
        )["transformed"]["bundle"]["containers"][0]["items"]

        albums = [
            (
                [unidecode(item.get("subHed", {}).get("name", "unknow"))],
                unidecode(item["source"]["hed"].replace("*", "")),
            )
            for item in json_data
        ]

        albums_to_return = search_and_get_best_albums(
            [album for album in albums if album[1]], self.ytmusic
        )

        return list(flatten(albums_to_return))


if __name__ == "__main__":
    headers = {
        "User-Agent": r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
    }
    from ytmusicapi import YTMusic

    scraper = Pitchfork(None, headers, YTMusic())
    homepage = scraper.get_service_homepage()

    # # get_playlist_tracks for "Album Review Page" - homepage[0]-[6]
    # gpt = scraper.get_playlist_tracks(homepage[5]["id"])
    # print(gpt)

    # get_playlist_details for "Lists and Guides" page - homepage[-1]
    gpd = scraper.get_playlists_details([homepage[-1]["id"][12:]])
    print(gpd)

    # # # get_playlist_tracks for "Albums" list with "headings" div
    # gpt = scraper.get_playlist_tracks(gpd[0]["id"])
    # print(gpt)

    # # get_playlist_tracks for "Albums" list without "headings" div
    # print(gpd[-5]["id"])
    # gpt = scraper.get_playlist_tracks(gpd[-5]["id"])
    # print(gpt)

    # get_playlist_tracks for "Songs" list
    print(gpd[4]["id"])
    gpt = scraper.get_playlist_tracks(gpd[4]["id"])
    print(gpt)
