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
        "albums": {
            "item": {
                "name": "script",
                "string": re.compile(
                    r"window\.__PRELOADED_STATE__\ \=\ (?P<json_data>.*)\;"
                ),
            },
        },
    }

    def get_playlists_details(self, playlists):
        match_LAG = re.match(r"^LAG\-(?P<ListAndGuidePage>.+)$", playlists[0])
        if match_LAG:
            logger.debug(f'matched "lists and guides page" {playlists[0]}')
            listAndGuidePage = match_LAG["ListAndGuidePage"]
            endpoint = f"{self.service_endpoint}/{listAndGuidePage}"
            data = self.session.get(endpoint)
            soup = bs(data.text, "html5lib")
            # links = soup.find_all("a", class_="title-link module__title-link")
            # lists = soup.find("section", class_="featured-lists").find_all(
            #     "li"
            # )
            lists = soup.find(
                "div",
                attrs={
                    "data-testid": "SummaryRiverWrapper"
                },  # "class": re.compile(r"summary-collection-grid")}
            ).find_all(
                "a", attrs={"class": re.compile(r"summary-item__hed-link")}
            )
            print([(listitem.text, listitem["href"]) for listitem in lists])

            list_dicts = []

            def job(listitem):
                track_dicts = []
                for atag in listitem.find_all("a"):
                    if atag.text == "Year in Music" or atag["href"].startswith(
                        "/topics/"
                    ):
                        data = self.session.get(
                            f"{self.service_endpoint}{atag['href']}"
                        )
                        soup = bs(data.text, "html5lib")
                        links = soup.find_all(
                            "a", class_="title-link module__title-link"
                        )
                        track_dicts.append(
                            {
                                "name": listitem.span.text + " Best Albums",
                                "id": f"YIMAlbums-{links[0]['href']}",
                            }
                        )
                        track_dicts.append(
                            {
                                "name": listitem.span.text + " Best Tracks",
                                "id": f"YIMTracks-{links[1]['href']}",
                            }
                        )
                    else:
                        track_dicts.append(
                            {
                                "name": listitem.span.text
                                + " Best "
                                + atag.text,
                                "id": f"{atag.text}-{atag['href']}",
                            }
                        )
                return track_dicts

            with ThreadPoolExecutor() as executor:
                # make sure order is deterministic so that rankings are preserved
                for listitem in executor.map(job, lists):
                    list_dicts.extend(listitem)

            return sorted(
                [dict(t) for t in {tuple(d.items()) for d in list_dicts}],
                key=lambda d: d["name"],
            )

    def get_playlist_tracks(self, playlist):
        # deal with album review pages
        # if re.match(r"^ARP\-(?P<albumId>.+)$", playlist):
        #     return self.get_playlists_details([playlist])

        match_ARP = re.match(r"^ARP\-(?P<reviewPage>.+)$", playlist)
        if match_ARP:
            logger.debug(f'matched "album review page" {playlist}')

            json_item = str(
                self._get_items_soup(f"/{match_ARP['reviewPage']}", "albums")[
                    0
                ].contents
            )

            json_script = self.service_schema["albums"]["item"][
                "string"
            ].search(json_item)

            json_data = json.loads(
                unidecode(
                    (json_script["json_data"]).encode().decode("unicode-escape")
                )
            )["transformed"]["bundle"]["containers"][0]["items"]

            # with open("/tmp/data.json", "w", encoding="utf-8") as f:
            #     json.dump(
            #         json_data,
            #         f,
            #         ensure_ascii=False,
            #         indent=4,
            #     )

            albums = [
                (
                    [item.get("subHed", {}).get("name", "unknow")],
                    item["source"]["hed"].replace("*", ""),
                )
                for item in json_data
            ]

            albums_to_return = search_and_get_best_albums(
                [album for album in albums if album[1]], self.ytmusic
            )

            return list(flatten(albums_to_return))

        # deal with lists and guides pages
        if re.match(r"^LAG\-(?P<albumId>.+)$", playlist):
            return self.get_playlists_details([playlist])

        # deal with albums pages
        match_Albums = re.match(r"^Albums\-(?P<albumsPage>.+)$", playlist)
        if match_Albums:
            playlist_results = []
            logger.info(f'matched "albums page" {playlist}')
            albumsPage = match_Albums["albumsPage"]
            endpoint = f"{self.service_endpoint}{albumsPage}"
            data = self.session.get(endpoint)
            soup = bs(data.text, "html5lib")
            pages = [
                page["href"]
                for page in soup.find_all(
                    "a", class_="fts-pagination__list-item__link"
                )
            ]

            def job(page):
                if albumsPage.startswith(f"{self.service_endpoint}/"):
                    endpoint = page
                else:
                    endpoint = f"{self.service_endpoint}{page}"

                data = self.session.get(endpoint)
                soup = bs(data.text, "html5lib")
                page_albums = []
                items = soup.find_all("div", class_="list-blurb__artist-work")
                if len(items) == 0:
                    items = [
                        item.text for item in soup.find_all("strong", class_="")
                    ]
                    # logger.info(len(items))
                    # if len(items) == 0:
                    #     return self.get_playlist_tracks(
                    #         playlist.replace("Albums", "YIMAlbums")
                    #     )
                    item_re = re.compile(
                        r"^\d{2,3}(\:|\.)\s(?P<artist>.+)\n(?P<album>.+)\n.+$"
                    )
                    # logger.info(items)
                    matched_items = [item_re.match(item) for item in items]
                    # logger.info(matched_items)
                    page_albums = [
                        ([item["artist"]], item["album"])
                        for item in matched_items
                        if item
                    ]
                    # logger.info(page_albums)
                    if len(page_albums) == 0:
                        artist_re = re.compile(
                            r"^\d{2,3}(\:|\.)\s(?P<artist>[^\_]+)"
                        )
                        items = soup.find_all("h2", text=artist_re)
                        items.extend(soup.find_all("p", text=artist_re))
                        # items.extend(soup.find_all("strong", text = artist_re))
                        items.extend(
                            [
                                item
                                for item in soup.find_all("strong")
                                if artist_re.match(item.text)
                            ]
                        )
                        # logger.info([artist_re.match(item.text)["artist"].split(' / ') for item in soup.find_all("strong") if artist_re.match(item.text)])
                        try:
                            page_albums = [
                                (
                                    artist_re.match(item.text)["artist"].split(
                                        " / "
                                    ),
                                    item.find_next_sibling("h2").text,
                                )
                                for item in items
                            ]
                        except:
                            page_albums = [
                                (
                                    artist_re.match(item.text)["artist"].split(
                                        " / "
                                    ),
                                    item.find_next("strong").text,
                                )
                                for item in items
                            ]
                        logger.info(page_albums)
                        # page_albums = [([artist_re.match(item.text)['artist']], item.find_next_sibling("h2").text) for item in items]

                    return page_albums

                for item in items:
                    artists = item.find(
                        "ul",
                        class_=re.compile(
                            r"(artist-links\s)?artist-list\slist-blurb__artists"
                        ),
                    ).find_all("li")
                    album = item.find(
                        "h2", class_="list-blurb__work-title"
                    ).text

                    artists_albumtitle = (
                        [artist.text for artist in artists],
                        album,
                    )
                    page_albums.append(artists_albumtitle)
                return page_albums

            if len(pages) == 1:
                playlist_results.extend(job(pages[0]))
            else:
                with ThreadPoolExecutor() as executor:
                    # make sure order is deterministic so that rankings are preserved
                    for page in executor.map(job, pages):
                        playlist_results.extend(page)

            albums_to_return = search_and_get_best_albums(
                [album for album in playlist_results if album[1]], self.ytmusic
            )

            return list(flatten(albums_to_return))

        # deal with tracks pages
        match_Tracks = re.match(r"^Tracks\-(?P<tracksPage>.+)$", playlist)
        if match_Tracks:
            logger.debug(f'matched "tracks page" {playlist}')
            tracksPage = match_Tracks["tracksPage"]
            endpoint = f"{self.service_endpoint}{tracksPage}"
            data = self.session.get(endpoint)
            soup = bs(data.text, "html5lib")
            pages = soup.find_all("a", class_="fts-pagination__list-item__link")

            tracks = []

            def job(page):
                track_dict = {}
                endpoint = (
                    f"{self.service_endpoint}/{tracksPage}?page={page.text}"
                )
                data = self.session.get(endpoint)
                soup = bs(data.text, "html5lib")
                # page_tracks = []
                items = soup.find_all("div", class_="list-blurb__artist-work")

                for index, item in enumerate(items):
                    song_artists = [
                        artist.text
                        for artist in item.select(
                            'ul[class*="artist-list list-blurb__artists"]'
                        )[0].find_all("li")
                    ]
                    song_name = unidecode(
                        item.find("h2", class_="list-blurb__work-title").text
                    ).replace('"', "")

                    track_dict[index] = {
                        "song_name": song_name,
                        "song_artists": song_artists,
                        "isrc": None,
                    }

                tracks = list(track_dict.values())
                print(f"total tracks for {playlist}: {len(tracks)}")
                return search_and_get_best_match(tracks, self.ytmusic)

            if len(pages) == 1:
                tracks.extend(job(pages[0]))
            else:
                with ThreadPoolExecutor() as executor:
                    # make sure order is deterministic so that rankings are preserved
                    for page in executor.map(job, pages):
                        tracks.extend(page)
            return tracks

        # deal with year in music tracks pages
        match_Tracks = re.match(r"^YIMTracks\-(?P<tracksPage>.+)$", playlist)
        if match_Tracks:
            logger.debug(f'matched "year in music tracks page" {playlist}')
            tracksPage = match_Tracks["tracksPage"]
            endpoint = f"{self.service_endpoint}/{tracksPage}"
            data = self.session.get(endpoint)
            soup = bs(data.text, "html5lib")
            items = soup.find_all("div", class_="list-blurb__artist-work")

            # mostly process in the same way as any list of tracks page
            if len(items) > 0:
                return self.get_playlist_tracks(
                    playlist.replace("YIMTracks", "Tracks")
                )

            # but not always.
            tracks = []
            track_dict = {}
            items = [
                unidecode(item.text) for item in soup.find_all("h2", class_="")
            ]
            item_re = re.compile(r"^(?P<artist>.+)\:\ \"(?P<title>.+)$")
            for index, item in enumerate(items):
                song_artists = [item_re.match(item)["artist"]]
                song_name = (
                    item_re.match(item)["title"].replace('"', "").strip()
                )

                track_dict[index] = {
                    "song_name": song_name,
                    "song_artists": song_artists,
                    "isrc": None,
                }

            tracks = list(track_dict.values())
            return search_and_get_best_match(tracks, self.ytmusic)

        # deal with year in music albums pages
        match_YIMAlbums = re.match(r"^YIMAlbums\-(?P<albumsPage>.+)$", playlist)
        if match_YIMAlbums:
            logger.info(f'matched "year in music albums page" {playlist}')
            albumsPage = match_YIMAlbums["albumsPage"]
            if albumsPage.startswith(self.service_endpoint):
                endpoint = albumsPage
            else:
                endpoint = f"{self.service_endpoint}/{albumsPage}"

            data = self.session.get(endpoint)
            soup = bs(data.text, "html5lib")
            items = soup.find_all("div", class_="list-blurb__artist-work")

            # mostly process in the same way as any list of albums page
            if len(items) > 0:
                return self.get_playlist_tracks(
                    playlist.replace("YIMAlbums", "Albums")
                )

            # but not always.
            items = [
                unidecode(item.text) for item in soup.find_all("h2", class_="")
            ]

            item_re = re.compile(r"^(?P<artist>.+)\:\ (\")?(?P<title>.+)$")
            matched_items = [item_re.match(item) for item in items]
            albums = [
                ([item["artist"]], item["title"]) for item in matched_items
            ]

            albums_to_return = search_and_get_best_albums(
                [album for album in albums if album[1]], self.ytmusic
            )

            return list(flatten(albums_to_return))

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
