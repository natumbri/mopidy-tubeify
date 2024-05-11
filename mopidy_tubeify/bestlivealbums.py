import json
import re

from bs4 import BeautifulSoup as bs

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import search_and_get_best_albums


class BestLiveAlbums(ServiceClient):
    service_uri = "bestlivealbums"
    service_name = "Best Live & Studio Albums Website"
    service_endpoint = "http://www.bestlivealbums.com"
    service_schema = {
        "live-album-polls": {
            "container": {"tag": "article", "attrs": {}},
            "item": {"tag": "ul", "attrs": {}},
        },
        "lists-of-best-live-albums": {
            "container": {"tag": "div", "attrs": {"class": "entry-content"}},
            "item": {"tag": "ol", "attrs": {}},
        },
        "homepage": {
            "container": {
                "tag": "div",
                "attrs": {"class": "menu-main-menu-container"},
            },
            "item": {
                "tag": "li",
                "attrs": {"class": re.compile(r"menu-item.*")},
            },
        },
        "poll": {"container": {"tag": "input", "attrs": {"name": "poll_id"}}},
        "nonce": {
            "container": {"tag": "input", "attrs": {"name": "wp-polls-nonce"}}
        },
        "album_artists": {
            "container": {"tag": "span", "attrs": {"class": "tags-links"}}
        },
    }

    def get_playlists_details(self, playlists):
        if playlists == ["/live-album-polls/"]:
            soup = self._get_items_soup(playlists[0], "live-album-polls")
            genres = [
                {
                    "name": page.a.text,
                    "id": f"genre-{page.a['href'].split(self.service_endpoint)[1]}",
                }
                for page in soup[0].find_all("li")
            ]

            artists = [
                {
                    "name": page.a.text,
                    "id": f"artist-{page.a['href'].split(self.service_endpoint)[1]}",
                }
                for page in soup[1].find_all("li")
            ]

            return genres + artists

        if playlists == ["/lists-of-best-live-albums/"]:
            soup = self._get_items_soup(
                playlists[0], "lists-of-best-live-albums"
            )
            return [
                {
                    "name": ordered_list.findPrevious("strong").text,
                    "id": f"list-{''.join(str(soup[0]).splitlines()).encode('utf-8').hex()}",  # hex-encode to avoid blowing up web intefaces
                }
                for ordered_list in soup
            ]

        logger.warn(f"no details, get_playlists_details: {playlists}")
        return []

    def get_playlist_tracks(self, playlist):
        # list- playlists include the album list items as json, to avoid
        # another call to the page where the playlist was located
        if re.match(r"^list-.*$", playlist):
            soup = [
                li
                for li in bs(
                    (bytes.fromhex(playlist[5:])).decode("utf-8"),
                    "html5lib",
                ).find_all("li")
                if li.find("a")
            ]
            albums = [
                (
                    [li.text.split(" by ")[1].strip()],
                    li.text.split(" by ")[0].strip(),
                )
                for li in soup
                if " by " in li.text
            ]

            alt_albums = [
                li.text.replace(" at ", "\\u00a0\\u00a0 \\u00a0").split(
                    "\\u00a0\\u00a0 \\u00a0"
                )
                for li in soup
            ]

            albums += [
                (alt_album[0], alt_album[1])
                for alt_album in alt_albums
                if len(alt_album) == 2
            ]

        else:
            # this re is currently set up for artist and genre
            match = re.match(
                r"^(?P<kind>(artist|genre))\-(?P<link>/.*best\-.*/$)", playlist
            )

            # artist and genre lists are similar to each other, except that
            # on artist pages, you have to get the artist separately and
            # then apply it to each item on the list
            if match["kind"] in ["artist", "genre"]:
                soup = self._get_items_soup(match["link"])
                poll = self._get_items_soup(soup, "poll")["value"]
                nonce = self._get_items_soup(soup, "nonce")
                album_artists = self._get_items_soup(soup, "album_artists")
                endpoint = f"{self.service_endpoint}/wp-admin/admin-ajax.php"
                data = {
                    "action": "polls",
                    "view": "result",
                    "poll_id": poll,
                    nonce["id"]: nonce["value"],
                }

                headers = self.session.headers
                headers.update(
                    {
                        # "Host": "www.bestlivealbums.com",
                        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0",
                        # "Accept": "*/*",
                        # "Accept-Language": "en-US,en;q=0.5",
                        # "Accept-Encoding": "gzip, deflate",
                        # "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                        "X-Requested-With": "XMLHttpRequest",
                        # "Content-Length": "60",
                        # "Origin": "http://www.bestlivealbums.com",
                        # "Connection": "keep-alive",
                        # "Referer": "http://www.bestlivealbums.com/best-aor-live-album/",
                        # "Cookie": "PHPSESSID=o3j7q2601kk3fta19tjs4fe8u4; 72120b8cae832756389e425d970d47b5=e607e5a5a816d0de37c7f0a4291d4121; ckon2308=sject2308_f2b66e763ec46; SJECT2308=CKON2308; JCS_INENREF=; JCS_INENTIM=1691235931116; _wpss_h_=1; _wpss_p_=N%3A5%20%7C%20WzFdW1BERiBWaWV3ZXJdIFsyXVtDaHJvbWUgUERGIFZpZXdlcl0gWzNdW0Nocm9taXVtIFBERiBWaWV3ZXJdIFs0XVtNaWNyb3NvZnQgRWRnZSBQREYgVmlld2VyXSBbNV1bV2ViS2l0IGJ1aWx0LWluIFBERl0g",
                        # "Pragma": "no-cache",
                        # "Cache-Control": "no-cache"
                    }
                )
                results = self.session.post(endpoint, data)

                soup = [
                    li
                    for li in bs(
                        results.content.decode("utf-8"), "html5lib"
                    ).find_all("li")
                    if li.find("a")
                ]

                album_names = [li.find("a").text for li in soup]

                if match["kind"] == "artist":
                    album_artists = [
                        album_artists.text.split("Live Albums")[0]
                        .replace("Tags", "")
                        .strip()
                    ] * len(soup)
                else:
                    album_artists = [
                        li.text.split(album_name)[0].strip()
                        for li, album_name in zip(soup, album_names)
                    ]

                albums = [
                    (
                        [album_artist],
                        album_name,
                    )
                    for album_artist, album_name in zip(
                        album_artists, album_names
                    )
                ]

        albums_to_return = search_and_get_best_albums(
            [album for album in albums if album[1]], self.ytmusic
        )

        if albums_to_return:
            return list(flatten(albums_to_return))

        logger.warn(f"no tracks, get_playlist_tracks: {playlist}")
        return

    def get_service_homepage(self):
        soup = self._get_items_soup("", "homepage")
        return [
            {
                "name": page.a.text,
                "id": f"listoflists-{page.a['href'].split(self.service_endpoint)[1]}",
            }
            for page in soup
        ]
