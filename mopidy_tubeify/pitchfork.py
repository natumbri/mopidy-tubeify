import json
import re
from concurrent.futures.thread import ThreadPoolExecutor

from bs4 import BeautifulSoup as bs
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

            # # No need for threading, if there is no waiting for IO
            # with ThreadPoolExecutor() as executor:
            #     # make sure order is deterministic so that rankings are preserved
            #     for listitem in executor.map(job, lists):
            #         list_dicts.extend(listitem)

            for listitem in map(job, lists):
                list_dicts.extend(listitem)

            # # Do we really want to sort these?
            # return sorted(
            #     [dict(t) for t in {tuple(d.items()) for d in list_dicts}],
            #     key=lambda d: d["name"],
            # )

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
            # endpoint = f"{self.service_endpoint}{match_Albums['albumsPage']}"
            # data = self.session.get(endpoint)
            # soup = bs(data.text, "html5lib")

            # # ususally, the artist: album is immediatly after a "heading-h3" "heading" div
            # listitems = [
            #     item.find_next("h2").text
            #     for item in soup.find_all(
            #         "div", attrs={"role": "heading", "class": "heading-h3"}
            #     )
            #     if item.find_next("h2")
            # ]

            # # but sometimes, there is no "heading" div
            # if not listitems:
            #     listitems = [item.text for item in soup.find_all("h2")]

            # albums = [
            #     (item.split(":")[0].split("/"), item.split(":")[1])
            #     for item in listitems
            #     if re.search(r".*\:\ .*", item)
            # ]

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

            # # The old approach to Albums pages
            # def job(page):
            #     if albumsPage.startswith(f"{self.service_endpoint}/"):
            #         endpoint = page
            #     else:
            #         endpoint = f"{self.service_endpoint}{page}"

            #     data = self.session.get(endpoint)
            #     soup = bs(data.text, "html5lib")
            #     page_albums = []
            #     items = soup.find_all("div", class_="list-blurb__artist-work")
            #     if len(items) == 0:
            #         items = [
            #             item.text for item in soup.find_all("strong", class_="")
            #         ]
            #         # logger.info(len(items))
            #         # if len(items) == 0:
            #         #     return self.get_playlist_tracks(
            #         #         playlist.replace("Albums", "YIMAlbums")
            #         #     )
            #         item_re = re.compile(
            #             r"^\d{2,3}(\:|\.)\s(?P<artist>.+)\n(?P<album>.+)\n.+$"
            #         )
            #         # logger.info(items)
            #         matched_items = [item_re.match(item) for item in items]
            #         # logger.info(matched_items)
            #         page_albums = [
            #             ([item["artist"]], item["album"])
            #             for item in matched_items
            #             if item
            #         ]
            #         # logger.info(page_albums)
            #         if len(page_albums) == 0:
            #             artist_re = re.compile(
            #                 r"^\d{2,3}(\:|\.)\s(?P<artist>[^\_]+)"
            #             )
            #             items = soup.find_all("h2", text=artist_re)
            #             items.extend(soup.find_all("p", text=artist_re))
            #             # items.extend(soup.find_all("strong", text = artist_re))
            #             items.extend(
            #                 [
            #                     item
            #                     for item in soup.find_all("strong")
            #                     if artist_re.match(item.text)
            #                 ]
            #             )
            #             # logger.info([artist_re.match(item.text)["artist"].split(' / ') for item in soup.find_all("strong") if artist_re.match(item.text)])
            #             try:
            #                 page_albums = [
            #                     (
            #                         artist_re.match(item.text)["artist"].split(
            #                             " / "
            #                         ),
            #                         item.find_next_sibling("h2").text,
            #                     )
            #                     for item in items
            #                 ]
            #             except:
            #                 page_albums = [
            #                     (
            #                         artist_re.match(item.text)["artist"].split(
            #                             " / "
            #                         ),
            #                         item.find_next("strong").text,
            #                     )
            #                     for item in items
            #                 ]
            #             logger.info(page_albums)
            #             # page_albums = [([artist_re.match(item.text)['artist']], item.find_next_sibling("h2").text) for item in items]

            #         return page_albums

            #     for item in items:
            #         artists = item.find(
            #             "ul",
            #             class_=re.compile(
            #                 r"(artist-links\s)?artist-list\slist-blurb__artists"
            #             ),
            #         ).find_all("li")
            #         album = item.find(
            #             "h2", class_="list-blurb__work-title"
            #         ).text

            #         artists_albumtitle = (
            #             [artist.text for artist in artists],
            #             album,
            #         )
            #         page_albums.append(artists_albumtitle)
            #     return page_albums

            # if len(pages) == 1:
            #     playlist_results.extend(job(pages[0]))
            # else:
            #     with ThreadPoolExecutor() as executor:
            #         # make sure order is deterministic so that rankings are preserved
            #         for page in executor.map(job, pages):
            #             playlist_results.extend(page)

            # albums_to_return = search_and_get_best_albums(
            #     [album for album in playlist_results if album[1]], self.ytmusic
            # )

            # return list(flatten(albums_to_return))

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

            # tracksPage = match_Tracks["tracksPage"]
            # endpoint = f"{self.service_endpoint}{tracksPage}"
            # data = self.session.get(endpoint)
            # soup = bs(data.text, "html5lib")
            # pages = soup.find_all("a", class_="fts-pagination__list-item__link")

            # tracks = []

            # def job(page):
            #     track_dict = {}
            #     endpoint = (
            #         f"{self.service_endpoint}/{tracksPage}?page={page.text}"
            #     )
            #     data = self.session.get(endpoint)
            #     soup = bs(data.text, "html5lib")
            #     # page_tracks = []
            #     items = soup.find_all("div", class_="list-blurb__artist-work")

            #     for index, item in enumerate(items):
            #         song_artists = [
            #             artist.text
            #             for artist in item.select(
            #                 'ul[class*="artist-list list-blurb__artists"]'
            #             )[0].find_all("li")
            #         ]
            #         song_name = unidecode(
            #             item.find("h2", class_="list-blurb__work-title").text
            #         ).replace('"', "")

            #         track_dict[index] = {
            #             "song_name": song_name,
            #             "song_artists": song_artists,
            #             "isrc": None,
            #         }

            #     tracks = list(track_dict.values())
            #     print(f"total tracks for {playlist}: {len(tracks)}")
            #     return search_and_get_best_match(tracks, self.ytmusic)

            # if len(pages) == 1:
            #     tracks.extend(job(pages[0]))
            # else:
            #     with ThreadPoolExecutor() as executor:
            #         # make sure order is deterministic so that rankings are preserved
            #         for page in executor.map(job, pages):
            #             tracks.extend(page)
            # return tracks

        # # deal with year in music tracks pages
        # match_Tracks = re.match(r"^YIMTracks\-(?P<tracksPage>.+)$", playlist)
        # if match_Tracks:
        #     logger.debug(f'matched "year in music tracks page" {playlist}')
        #     tracksPage = match_Tracks["tracksPage"]
        #     endpoint = f"{self.service_endpoint}/{tracksPage}"
        #     data = self.session.get(endpoint)
        #     soup = bs(data.text, "html5lib")
        #     items = soup.find_all("div", class_="list-blurb__artist-work")

        #     # mostly process in the same way as any list of tracks page
        #     if len(items) > 0:
        #         return self.get_playlist_tracks(
        #             playlist.replace("YIMTracks", "Tracks")
        #         )

        #     # but not always.
        #     tracks = []
        #     track_dict = {}
        #     items = [
        #         unidecode(item.text) for item in soup.find_all("h2", class_="")
        #     ]
        #     item_re = re.compile(r"^(?P<artist>.+)\:\ \"(?P<title>.+)$")
        #     for index, item in enumerate(items):
        #         song_artists = [item_re.match(item)["artist"]]
        #         song_name = (
        #             item_re.match(item)["title"].replace('"', "").strip()
        #         )

        #         track_dict[index] = {
        #             "song_name": song_name,
        #             "song_artists": song_artists,
        #             "isrc": None,
        #         }

        #     tracks = list(track_dict.values())
        #     return search_and_get_best_match(tracks, self.ytmusic)

        # # deal with year in music albums pages
        # match_YIMAlbums = re.match(r"^YIMAlbums\-(?P<albumsPage>.+)$", playlist)
        # if match_YIMAlbums:
        #     logger.info(f'matched "year in music albums page" {playlist}')
        #     albumsPage = match_YIMAlbums["albumsPage"]
        #     if albumsPage.startswith(self.service_endpoint):
        #         endpoint = albumsPage
        #     else:
        #         endpoint = f"{self.service_endpoint}/{albumsPage}"

        #     data = self.session.get(endpoint)
        #     soup = bs(data.text, "html5lib")
        #     items = soup.find_all("div", class_="list-blurb__artist-work")

        #     # mostly process in the same way as any list of albums page
        #     if len(items) > 0:
        #         return self.get_playlist_tracks(
        #             playlist.replace("YIMAlbums", "Albums")
        #         )

        #     # but not always.
        #     items = [
        #         unidecode(item.text) for item in soup.find_all("h2", class_="")
        #     ]

        #     item_re = re.compile(r"^(?P<artist>.+)\:\ (\")?(?P<title>.+)$")
        #     matched_items = [item_re.match(item) for item in items]
        #     albums = [
        #         ([item["artist"]], item["title"]) for item in matched_items
        #     ]

        #     albums_to_return = search_and_get_best_albums(
        #         [album for album in albums if album[1]], self.ytmusic
        #     )

        #     return list(flatten(albums_to_return))

        # album = self.ytmusic.get_album(playlist)
        # tracks = album["tracks"]
        # fields = ["artists", "thumbnails"]
        # [
        #     track.update({field: album[field]})
        #     for field in fields
        #     for track in tracks
        #     if track[field] is None
        # ]
        # [
        #     track.update(
        #         {
        #             "album": {
        #                 "name": album["title"],
        #                 "id": playlist,
        #             }
        #         }
        #     )
        #     for track in tracks
        # ]
        # return tracks

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

    # # gpt = scraper.get_playlist_tracks(
    # #     "bad-bunny-essentials/pl.1c35ac10cfe848aaa19f68ebe62ea46e"
    # # )
    # # print(gpt)
    # # print(scraper.get_playlist_tracks(gpt[0]['id']))

    # # gud = scraper.get_users_details(["npr-music/1437679561"])
    # # print(gud)
