import re

from bs4 import BeautifulSoup as bs

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import search_and_get_best_albums


class Discogs(ServiceClient):
    service_uri = "discogs"
    service_name = "Discogs"
    service_image = "https://upload.wikimedia.org/wikipedia/commons/thumb/6/69/Discogs_record_icon.svg/512px-Discogs_record_icon.svg.png"
    service_endpoint = "https://www.discogs.com"

    def get_playlist_tracks(self, playlist):
        filtered_items = None
        match_DGP = re.match(r"^DGP\-(?P<dgppage>.+)$", playlist)

        # deal with discogs pages
        if match_DGP:
            logger.debug(f'matched "discogs page:" {playlist}')
            playlist = match_DGP["dgppage"]
            endpoint = f"{self.service_endpoint}/digs/{playlist}"

            data = self.session.get(endpoint)
            soup = bs(data.text, "html5lib")

            filtered_items = soup.find_all("div", class_="release-block-text")

            # deal with pages where there is a table
            album_tables = soup.find_all("table")
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
                    "filterValue": None,
                    "filterType": None,
                    "widgetBlockId": None,
                    "wpnonce": None,
                },
            ).text

            soup = bs(data, "html5lib")
            divs += soup.find_all("div", attrs={"class": "ultp-block-content"})
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
