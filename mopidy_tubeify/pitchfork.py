import json
import re
from concurrent.futures.thread import ThreadPoolExecutor

from bs4 import BeautifulSoup as bs
from unidecode import unidecode

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import (
    search_and_get_best_album,
    search_and_get_best_albums,
    search_and_get_best_match,
)


class Pitchfork(ServiceClient):
    def get_playlists_details(self, playlists):
        logger.info(playlists)

        def job(playlist):

            # # for album review pages
            # match_ARP = re.match(r"^ARP\-(?P<reviewPage>.+)$", playlist)
            # if match_ARP:
            #     logger.debug(f'matched "album review page" {playlist}')
            #     reviewPage = match_ARP["reviewPage"]
            #     endpoint = f"https://pitchfork.com/{reviewPage}"
            #     data = self.session.get(endpoint)
            #     soup = bs(data.text, "html5lib")
            #     script_re = re.compile(r"^window.App=(?P<json_data>.*);$")
            #     json_script = soup.find("script", string=script_re)
            #     json_data = json.loads(
            #         script_re.match(json_script.text)["json_data"]
            #     )["context"]["dispatcher"]["stores"]["ReviewsStore"]["items"]

            #     item_list = [
            #         json_data[item]["tombstone"]["albums"][0]["album"]
            #         for item in json_data
            #     ]

            #     playlist_results = []

            #     for item in item_list:

            #         if not item["artists"]:

            #             # is there something better than 'unknown'?
            #             # if re.search('Various Artists', item['photos']['tout']['title']):
            #             #     item["artists"].append(
            #             #         {"display_name": "Various Artists"}
            #             #     )
            #             # else:

            #             logger.warn(
            #                 f"expect wrong album: no artists listed for {item}"
            #             )

            #             item["artists"].append(
            #                 {
            #                     "display_name": "Unknown"
            #                 }  # str(item["release_year"])}
            #             )
            #             album = f"'{item['display_name']}'"
            #         else:
            #             album = f"{item['artists'][0]['display_name']}, '{item['display_name']}'"

            #         artists_albumtitle = (
            #             [artist["display_name"] for artist in item["artists"]],
            #             item["display_name"],
            #         )

            #         best_album_result = search_and_get_best_album(
            #             artists_albumtitle, self.ytmusic
            #         )
            #         if best_album_result:
            #             playlist_results.append(
            #                 {
            #                     "name": album,
            #                     "id": best_album_result[0]["browseId"],
            #                 }
            #             )
            #     return playlist_results

            # for lists and guides pages
            match_LAG = re.match(r"^LAG\-(?P<ListAndGuidePage>.+)$", playlist)
            if match_LAG:
                logger.debug(f'matched "lists and guides page" {playlist}')
                listAndGuidePage = match_LAG["ListAndGuidePage"]
                endpoint = f"https://pitchfork.com/{listAndGuidePage}"
                data = self.session.get(endpoint)
                soup = bs(data.text, "html5lib")
                links = soup.find_all(
                    "a", class_="title-link module__title-link"
                )
                lists = soup.find("section", class_="featured-lists").find_all(
                    "li"
                )

                track_dicts = []

                for listitem in lists:
                    for atag in listitem.find_all("a"):
                        if atag.text == "Year in Music":
                            data = self.session.get(
                                f"https://pitchfork.com{atag['href']}"
                            )
                            soup = bs(data.text, "html5lib")
                            links = soup.find_all(
                                "a", class_="title-link module__title-link"
                            )
                            track_dicts.append(
                                {
                                    "name": listitem.span.text + " Best Albums",
                                    "id": f"listoflists-YIMAlbums-{links[0]['href']}",
                                    # "id": f"listoflists-Albums-{links[0]['href']}",
                                }
                            )
                            track_dicts.append(
                                {
                                    "name": listitem.span.text + " Best Tracks",
                                    "id": f"YIMTracks-{links[1]['href']}",
                                }
                            )
                        else:
                            item_name = (
                                listitem.span.text + " Best " + atag.text
                            )
                            if atag.text == "Tracks":
                                item_id = f"{atag.text}-{atag['href']}"
                            else:
                                item_id = (
                                    f"listoflists-{atag.text}-{atag['href']}"
                                )

                            track_dicts.append(
                                {
                                    "name": item_name,
                                    "id": item_id,
                                }
                            )

                return track_dicts

            # for lists and guides pages
            match_Albums = re.match(r"^Albums\-(?P<albumsPage>.+)$", playlist)
            if match_Albums:
                logger.info(f'matched "albums page" {playlist}')
                albumsPage = match_Albums["albumsPage"]
                endpoint = f"https://pitchfork.com/{albumsPage}"
                data = self.session.get(endpoint)
                soup = bs(data.text, "html5lib")
                pages = soup.find_all(
                    "a", class_="fts-pagination__list-item__link"
                )

                playlist_results = []

                def job(page):
                    endpoint = (
                        f"https://pitchfork.com/{albumsPage}?page={page.text}"
                    )
                    data = self.session.get(endpoint)
                    soup = bs(data.text, "html5lib")
                    page_albums = []
                    items = soup.find_all(
                        "div", class_="list-blurb__artist-work"
                    )
                    for item in items:
                        artists = item.find(
                            "ul",
                            class_="artist-links artist-list list-blurb__artists",
                        ).find_all("li")
                        album = item.find(
                            "h2", class_="list-blurb__work-title"
                        ).text

                        artists_albumtitle = (
                            [artist.text for artist in artists],
                            album,
                        )
                        best_album_result = search_and_get_best_album(
                            artists_albumtitle, self.ytmusic
                        )
                        if best_album_result:
                            page_albums.append(
                                {
                                    "name": album,
                                    "id": best_album_result[0]["browseId"],
                                }
                            )
                    return page_albums

                if len(pages) == 1:
                    playlist_results.extend(job(pages[0]))
                else:
                    with ThreadPoolExecutor() as executor:
                        # make sure order is deterministic so that rankings are preserved
                        for page in executor.map(job, pages):
                            playlist_results.extend(page)

                return playlist_results

        results = []

        # does pitchfork uses a captcha? be careful before going multi-threaded
        [results.append(job(playlist)) for playlist in playlists]

        return list(flatten(results))

    def get_playlist_tracks(self, playlist):

        # deal with album review pages
        # if re.match(r"^ARP\-(?P<albumId>.+)$", playlist):
        #     return self.get_playlists_details([playlist])

        match_ARP = re.match(r"^ARP\-(?P<reviewPage>.+)$", playlist)
        if match_ARP:
            logger.debug(f'matched "album review page" {playlist}')
            reviewPage = match_ARP["reviewPage"]
            endpoint = f"https://pitchfork.com/{reviewPage}"
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

            albums = []

            for item in item_list:
                if not item["artists"]:
                    logger.warn(
                        f"expect wrong album: no artists listed for {item}"
                    )
                    item["artists"].append(
                        {
                            "display_name": "Unknown"
                        }  # str(item["release_year"])}
                    )

                albums.append(
                    (
                        [artist["display_name"] for artist in item["artists"]],
                        item["display_name"],
                    )
                )

            albums_to_return = search_and_get_best_albums(
                [album for album in albums if album[1]], self.ytmusic
            )

            return list(flatten(albums_to_return))

        # deal with lists and guides pages
        if re.match(r"^LAG\-(?P<albumId>.+)$", playlist):
            return self.get_playlists_details([playlist])

        # deal with albums pages
        if re.match(r"^Albums\-(?P<albumsPage>.+)$", playlist):
            return self.get_playlists_details([playlist])

        # deal with tracks pages
        match_Tracks = re.match(r"^Tracks\-(?P<tracksPage>.+)$", playlist)
        if match_Tracks:
            logger.debug(f'matched "tracks page" {playlist}')
            tracksPage = match_Tracks["tracksPage"]
            endpoint = f"https://pitchfork.com/{tracksPage}"
            data = self.session.get(endpoint)
            soup = bs(data.text, "html5lib")
            pages = soup.find_all("a", class_="fts-pagination__list-item__link")

            tracks = []

            def job(page):
                track_dict = {}
                endpoint = (
                    f"https://pitchfork.com/{tracksPage}?page={page.text}"
                )
                data = self.session.get(endpoint)
                soup = bs(data.text, "html5lib")
                # page_tracks = []
                items = soup.find_all("div", class_="list-blurb__artist-work")
                print(endpoint)
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
            endpoint = f"https://pitchfork.com/{tracksPage}"
            data = self.session.get(endpoint)
            soup = bs(data.text, "html5lib")
            items = soup.find_all("div", class_="list-blurb__artist-work")
            if len(items) > 0:
                return self.get_playlist_tracks(
                    playlist.replace("YIMTracks", "Tracks")
                )

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
                "id": r"ARP-best/high-scoring-albums/?page=1",
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
