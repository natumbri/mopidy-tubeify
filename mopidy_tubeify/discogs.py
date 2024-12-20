import re
from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import search_and_get_best_albums


class Discogs(ServiceClient):
    service_uri = "discogs"
    service_name = "Discogs"
    service_image = "https://upload.wikimedia.org/wikipedia/commons/thumb/6/69/Discogs_record_icon.svg/512px-Discogs_record_icon.svg.png"
    service_endpoint = "https://www.discogs.com"

    service_schema = {
        "digs_lists": {
            "container": {
                "name": "div",
                "attrs": {"class": "ultp-block-wrapper"},
            },
            "item": {
                "name": "h2",
                "attrs": {"class": re.compile(r"ultp-block-title")},
            },
        },
        "dgp_page_items": {
            "item": {"name": "div", "attrs": {"class": "release-block-text"}}
        },
        "dgp_page_tables": {"item": {"name": "table"}},
        "divs": {
            "item": {"name": "div", "attrs": {"class": "ultp-block-content"}}
        },
    }

    def get_playlist_tracks(self, playlist):
        filtered_items = None
        match_DGP = re.match(r"^DGP\-(?P<dgppage>.+)$", playlist)

        # deal with discogs pages
        if match_DGP:
            logger.debug(f'matched "discogs page:" {playlist}')
            playlist = match_DGP["dgppage"]
            endpoint = f"{self.service_endpoint}/digs/{playlist}/"
            data = self.session.get(endpoint)

            if re.search("Just a moment", data.text):
                raise Exception("Discogs page is looking for a cookie or something")
            
            new_url = re.findall(
                r"cUPMDTk\:\ \"(?P<url>[^\"]*)\"", str(soup.find("script"))
            )[0].replace(
                "\/", "/"
            )  # sometimes there is a 'please wait' catchpa

            # filtered_items = soup.find_all("div", class_="release-block-text")
            filtered_items = self._get_items_soup(data, "dgp_page_items")

            # deal with pages where there is a table
            # album_tables = soup.find_all("table")
            album_tables = self._get_items_soup(data, "dgp_page_tables")

            print(album_tables)
            if album_tables:
                album_table = album_tables[-1]
                result = []
                keys = [i.text for i in album_table.thead.tr.find_all("th")]

                for table_row in album_table.tbody.find_all("tr"):
                    vals = [i.text for i in table_row.find_all("td")]
                    result.append(dict(zip(keys, vals)))

                if len(result) > len(filtered_items):
                    albums = [
                        (
                            item.get(
                                "Artist(s)",
                                item.get("Artist", "Unknown Artist"),
                            ),
                            item.get("Title", item.get("Release", "Unknown")),
                        )
                        for item in result
                    ]
                    albums_to_return = search_and_get_best_albums(
                        albums, self.ytmusic
                    )
                    return list(flatten(albums_to_return))

        if filtered_items:
            albums = [
                (
                    item.find(
                        "div",
                        class_=re.compile(r".*release(?:-block)?-artist.*"),
                    )
                    .text.strip()
                    .split(" / "),
                    item.find(
                        "div",
                        class_=re.compile(r".*release(?:-block)?-title.*"),
                    ).text.strip(),
                )
                for item in filtered_items
            ]

            albums_to_return = search_and_get_best_albums(
                [album for album in albums if album[1]], self.ytmusic
            )

            return list(flatten(albums_to_return))

        # deal with other things
        return

    def get_service_homepage(self):
        # this is derived from the "Load More" button on /digs/music/
        endpoint = r"https://content.discogs.com/digs/wp-admin/admin-ajax.php"
        divs = []
        i = 1
        while len(divs) < 25:
            data = self.session.post(
                endpoint,
                data={
                    "action": "ultp_next_prev",
                    "paged": i,
                    "blockId": "af59cd",
                    "postId": 31133,
                    "blockName": "ultimate-post_post-grid-1",
                    "wpnonce": "a4923b142e",  # need to work out where this comes from, and generate it
                    # # the keys below are not needed?
                    # "filterValue": None,
                    # "filterType": None,
                    # "widgetBlockId": None,
                    # "ultpUniqueIds": {
                    #     # "group1": [44985, 44986, 44993],
                    #     # "group2": [44993, 45027, 44975],
                    #     # "group3": [44985, 44986, 44903],
                    #     # "group4": [44432, 43638, 43491],
                    #     # "group5": [42197, 98, 41830],
                    # },
                },
            )
            if data.text == "0":
                logger.warning("Discogs scrape failed")
                raise Exception()  # this is broken, probably because wpnonce is wrong

            divs += self._get_items_soup(data, "divs")
            i += 1

        page_divs = []
        for div in divs:
            page_divs.extend(div.find_all("a"))

        page_dicts = [
            {"title": div.text, "href": div["href"]} for div in page_divs if div
        ]

        page_results = [
            {
                "name": f"{page_dict['title']}",
                "id": f"DGP-{page_dict['href'].split(r'/')[-3]}/{page_dict['href'].split(r'/')[-2]}",
            }
            for page_dict in page_dicts
        ]

        return page_results


if __name__ == "__main__":
    headers = {
        "User-Agent": r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
    }
    from ytmusicapi import YTMusic

    scraper = Discogs(None, headers, YTMusic())
    homepage = scraper.get_service_homepage()
    print(homepage[0])
    gpt = scraper.get_playlist_tracks(homepage[0]["id"])

    print(gpt)
