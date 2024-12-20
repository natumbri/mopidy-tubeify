import re
from unidecode import unidecode
from mopidy_tubeify import logger
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import search_and_get_best_match


class Apple(ServiceClient):
    playlist_regex = re.compile(r"^.*\/?(?P<playlistid>pl\..+$)")

    service_uri = "applemusic"
    service_name = "Apple Music"
    service_image = "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5f/Apple_Music_icon.svg/200px-Apple_Music_icon.svg.png"
    service_endpoint = "https://music.apple.com"
    service_schema = {
        "homepage": {
            "item": {
                "name": "li",
                "attrs": {
                    # "role": "listitem",
                    "class": re.compile(r"shelf-grid__list-item"),
                },
            },
        },
        "playlist": {"container": {"name": "title", "attrs": {}}},
        "script": {
            "container": {"name": "script", "attrs": {"type": "module"}}
        },
        "user": {"container": {"name": "title", "attrs": {}}},
    }

    def get_applemusic_headers(self, endpoint=service_endpoint):
        # Getting the access token first to send it with the header to the api endpoint
        js = self._get_items_soup("/browse", "script")
        page = self.session.get(f"{endpoint}/{js['src']}")

        # is the access token always a 268 character long constant
        # with a 2 letter name?
        access_token_text = re.search(
            r"const [a-zA-Z]{2}=\"([^\"]{268})\"", page.text
        ).group(1)

        # access_token_tag = soup.find(
        #     "meta", {"name": "desktop-music-app/config/environment"}
        # )
        # json_obj = json.loads(unquote(access_token_tag["content"]))
        # access_token_text = json_obj["MEDIA_API"]["token"]

        # found in one of the js loaded in the head of music.apple.com
        # <script crossorigin="" src="/assets/index.84424de2.js" type="module"></script>
        # does it change from time to time?
        # access_token_text = "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IldlYlBsYXlLaWQifQ.eyJpc3MiOiJBTVBXZWJQbGF5IiwiaWF0IjoxNjg0MjUyNDc2LCJleHAiOjE2OTE1MTAwNzYsInJvb3RfaHR0cHNfb3JpZ2luIjpbImFwcGxlLmNvbSJdfQ.wB2ohAu70F2D7I5upABXSzYtyz6hjiTI1hw_gO4HPpEX07Cx8KfzxmQCkbsXjD8ZooiupQ3XVsctauM8pn1DQg"

        self.session.headers.update(
            {
                "authorization": f"Bearer {access_token_text}",
                "referer": endpoint,
                "accept": "application/json",
                "app-platform": "WebPlayer",
                "origin": endpoint,
            }
        )

    def get_users_details(self, users):
        def job(user):
            user_name = self._get_items_soup(f"/us/curator/{user}", "user").text
            return {"id": user, "name": user_name}

        results = []

        [results.append(job(user)) for user in users]
        return results

    def get_user_playlists(self, user):
        self.get_applemusic_headers()
        userId_re = re.compile(r".+/(?P<userId>\d{10})$")
        userId = userId_re.match(user)["userId"]
        endpoint = f"https://amp-api.music.apple.com/v1/catalog/us/curators/{userId}/playlists?offset=0"

        playlists = []

        while True:
            data = self.session.get(endpoint).json()
            playlists.extend(data["data"])
            if "next" in data:
                endpoint = f"https://amp-api.music.apple.com/{data['next']}"
            else:
                break

        return [
            {
                "name": playlist["attributes"]["name"],
                "id": playlist["attributes"]["url"].removeprefix(
                    f"{self.service_endpoint}/us/playlist/"
                ),
            }
            for playlist in playlists
        ]

    def get_playlists_details(self, playlists):
        def job(playlist):
            playlist_name = self._get_items_soup(
                f"/us/playlist/{playlist.split('/')[1]}", "playlist"
            ).text
            return {"name": playlist_name, "id": playlist}

        results = []

        # does apple uses a captcha? be careful before going multi-threaded
        [results.append(job(playlist)) for playlist in playlists]

        return results

    def get_playlist_tracks(self, playlist):
        track_dict = {}

        # # for scraping the playlist endpoint
        # endpoint = f"https://music.apple.com/us/playlist/{playlist}"
        # data = self.session.get(endpoint)
        # soup = bs(data.content.decode('utf-8'), "html5lib")

        # # sometimes the playlist endpoint has a  script that seems to
        # # have a json record of all the tracks  in the playlist, with
        # # information including title, duration, album, etc for each
        # track_list = (
        #     soup.find("script", {"id": "shoebox-media-api-cache-amp-music"})
        #     .text.encode("ascii", "ignore")
        #     .decode("unicode_escape")
        # )
        # content_re = re.compile(
        #     r"^.+platform\.web[^\[]+(?P<content>.+\])\}\"\}$"
        # )
        # extracted_content = content_re.match(track_list)
        # content_dict = json.loads(extracted_content["content"])
        # content_tracks = content_dict[0]["relationships"]["tracks"]["data"]

        # # sometimes you can just search the playlist endpoint for the isrc
        # isrc_pattern = re.compile(r'"isrc"\:"(?P<isrc>.{12})"')
        # isrcs = [match["isrc"] for match in isrc_pattern.finditer(track_list)]

        # # sometimes you can look for songs-list-rows and get the data from
        # # there. but there is no isrc
        # slr_re = re.compile(r"songs-list-row")
        # slrs = soup.find_all("div", {"role": "row", "class": slr_re.match})
        # content_tracks = [
        #     {
        #         "attributes": {
        #             "name": unidecode(
        #                 slr.find(
        #                     "div",
        #                     {
        #                         "class": re.compile(
        #                             "songs-list-row__song-name-wrapper .*"
        #                         )
        #                     },
        #                 )
        #                 .find(text=True)
        #                 .text.replace("\n", "")
        #                 .strip()
        #             ),
        #             "artistName": unidecode(
        #                 slr.find(
        #                     "div",
        #                     {
        #                         "class": re.compile(
        #                             "songs-list__song-link-wrapper .*"
        #                         )
        #                     },
        #                 )
        #                 .text.replace("\n", "")
        #                 .strip()
        #             ),
        #             "durationInMillis": ISO8601_to_seconds(
        #                 slr.find("time")["datetime"]
        #             )
        #             * 1000,
        #             "isrc": None,
        #         }
        #     }
        #     for slr in slrs
        # ]

        # best results seem to be from using the applemusic api.  but that
        # relies on the authentication headers working properly.
        self.get_applemusic_headers()

        # for the API endpoint, only need the playlist id
        endpoint = f'https://amp-api.music.apple.com/v1/catalog/us/playlists/{self.playlist_regex.match(playlist)["playlistid"]}'
        data = self.session.get(endpoint).json()
        content_tracks = data["data"][0]["relationships"]["tracks"]["data"]

        for index, track in enumerate(content_tracks):
            song_name = track["attributes"]["name"]
            song_artists = [track["attributes"]["artistName"]]
            song_duration = track["attributes"]["durationInMillis"] // 1000
            isrc = track["attributes"]["isrc"]

            track_dict[index] = {
                "song_name": song_name,
                "song_artists": song_artists,
                "song_duration": song_duration,
                "isrc": isrc,
            }

        tracks = list(track_dict.values())
        logger.debug(f"total tracks for {playlist}: {len(tracks)}")
        return search_and_get_best_match(tracks, self.ytmusic)

    def get_service_homepage(self):
        # # it is possible to get editorial data using the apple music api
        # # but there is quite a lot to work through
        # self.get_applemusic_headers()
        # endpoint = f"https://amp-api.music.apple.com/v1/editorial/us/groupings?platform=web&name=music"
        # data = self.session.get(endpoint).json()
        # with open('/tmp/apple-homepage-data.json', 'w') as f:
        #     json.dump(data, f)

        # content_re = re.compile(
        #     r"^.+platform\.web[^\[]+(?P<content>.+\])\}\"\}$"
        # )

        # endpoint = f"{self.service_endpoint}/us/browse"
        # data = self.session.get(endpoint)
        # soup = bs(data.content.decode("utf-8"), "html5lib")

        # # this script seems to have a json record of all the tracks
        # # in the playlist, with information including title, duration,
        # # album, etc for each
        # content_script = (
        #     soup.find("script", {"id": "shoebox-media-api-cache-amp-music"})
        #     .text.encode("ascii", "ignore")
        #     .decode("unicode_escape")
        # )
        # extracted_content = content_re.match(content_script)
        # content = json.loads(extracted_content["content"])
        # playlists = list(find_in_obj(content, "type", "playlists"))

        # sgli_re = re.compile(r"shelf-grid__list-item")
        # sglis = soup.find_all(
        #     "li", {"role": "listitem", "class": sgli_re.match}
        # )
        sglis = self._get_items_soup("/us/browse", "homepage")
        playlists = [
            {
                "attributes": {
                    "url": sgli.find("a")["href"],
                    "name": unidecode(
                        sgli.find("a").text.replace("\n", "").strip()
                    ),
                    "picture": sgli.find("picture")
                    .source["srcset"]
                    .split(" ")[0],
                }
            }
            for sgli in sglis
            if sgli.find("a")
        ]

        track_dicts = []

        for playlist in playlists:
            playlistid = self.playlist_regex.match(
                playlist["attributes"]["url"]
            )
            if playlistid:
                self.uri_images[playlistid["playlistid"]] = playlist[
                    "attributes"
                ]["picture"]
                track_dicts.append(
                    {
                        "name": playlist["attributes"]["name"],
                        "id": playlistid["playlistid"],
                    }
                )

        return track_dicts


if __name__ == "__main__":
    headers = {
        "User-Agent": r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
    }
    from ytmusicapi import YTMusic

    scraper = Apple(None, headers, YTMusic())

    homepage = scraper.get_service_homepage()
    print(homepage)
    # print(homepage[0])
    # print([homepage[0]["id"]])
    # gpd = scraper.get_playlists_details([homepage[0]["id"]])
    # print(gpd)
    # print(gpd[0]["id"])
    # gpt = scraper.get_playlist_tracks(gpd[0]["id"])
    # print(gpt)
    # # gpt = scraper.get_playlist_tracks(
    # #     "bad-bunny-essentials/pl.1c35ac10cfe848aaa19f68ebe62ea46e"
    # # )
    # # print(gpt)
    # # print(scraper.get_playlist_tracks(gpt[0]['id']))

    # # gud = scraper.get_users_details(["npr-music/1437679561"])
    # # print(gud)
