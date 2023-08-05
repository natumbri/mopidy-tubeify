import re

from bs4 import BeautifulSoup as bs

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import search_and_get_best_albums


class BestLiveAlbums(ServiceClient):
    service_uri = "bestlivealbums"
    service_name = "Best Live & Studio Albums"
    service_endpoint = "http://www.bestlivealbums.com"

    def get_playlists_details(self, playlists):
        if playlists == ["/live-album-polls/"]:
            endpoint = f"{self.service_endpoint}{playlists[0]}"
            data = self.session.get(endpoint)
            soup = (
                bs(data.content.decode("utf-8"), "html5lib")
                .find("article")
                .find_all("ul")
            )

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

        logger.warn(f"no details, get_playlists_details: {playlists}")
        return []

    def get_playlist_tracks(self, playlist):
        match = re.match(
            r"^(?P<kind>(artist|genre))\-(?P<link>/.*best\-.*/$)", playlist
        )
        if match:
            endpoint = f"{self.service_endpoint}{match['link']}"
            data = self.session.get(endpoint)
            soup = bs(data.content.decode("utf-8"), "html5lib")
            poll = soup.find("input", attrs={"name": "poll_id"})["value"]
            nonce = soup.find("input", attrs={"name": "wp-polls-nonce"})
            if match["kind"] == "artist":
                artist = (
                    soup.find("span", attrs={"class": "tags-links"})
                    .text.split("Live Albums")[0]
                    .replace("Tags", "")
                    .strip()
                )

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

            soup = bs(results.content.decode("utf-8"), "html5lib").find_all(
                "li"
            )

            if match["kind"] == "artist":
                albums = [
                    (
                        [artist],
                        li.find("a").text,
                    )
                    for li in soup
                    if li.find("a")
                ]

            else:
                albums = [
                    (
                        [li.text.split(li.find("a").text)[0].strip()],
                        li.find("a").text,
                    )
                    for li in soup
                    if li.find("a")
                ]

            albums_to_return = search_and_get_best_albums(
                [album for album in albums if album[1]], self.ytmusic
            )

            return list(flatten(albums_to_return))

        logger.warn(f"no tracks, get_playlist_tracks: {playlist}")
        return

    def get_service_homepage(self):
        endpoint = self.service_endpoint
        data = self.session.get(endpoint)

        soup = (
            bs(data.content.decode("utf-8"), "html5lib")
            .find("div", attrs={"class": "menu-main-menu-container"})
            .find_all("li", attrs={"class": re.compile(r"menu-item.*")})
        )

        return [
            {
                "name": page.a.text,
                "id": f"listoflists-{page.a['href'].split(self.service_endpoint)[1]}",
            }
            for page in soup
        ]
