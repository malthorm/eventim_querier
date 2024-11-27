import re
from datetime import datetime
from time import sleep

import requests
from pydantic import AnyHttpUrl, BaseModel
from pydantic_core import ValidationError
from requests.exceptions import Timeout

ARTISTS = [
    # artists you wanna see go here
    # "Charlie Hunter",
    # "Kurt Elling",
    # "Ezra Collective",
]

CITIES = [
    # if you're only interested in events in specific cities, you can name them here
    # if empty, all cities will be listed
    # "Karlsruhe",
    # "Stuttgart",
]

config = {
    "endpoint": "https://public-api.eventim.com/websearch/search/api/exploration/v1/products",
    "markdown_path": "events.md",
    "headers": {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0",
    },
    # follows: https://gist.github.com/DeveloperMarius/7e8aff4c69ccbf59238d76163c86d9c9
    "queryParams": {
        "webId": "web__eventim-de",
        "language": "de",
        "page": 1,
        "sort": "NameAsc",
        "top": 50,
        "search_term": "",
        "retail_partner": "",
        "in_stock": None,
        "tags": [],
        "city_names": tuple(),
        "categories": [],
        "date_from": None,
        "date_to": None,
        "time_from": None,
        "time_to": None,
    },
}


class Location(BaseModel):
    name: str
    city: str
    postal_code: int | None = None


class LiveEntertainment(BaseModel):
    startDate: datetime
    location: Location


class TypeAttributes(BaseModel):
    liveEntertainment: LiveEntertainment


class LiveEvent(BaseModel):
    productId: int
    name: str
    description: str = ""
    price: float | None = None
    inStock: bool
    link: AnyHttpUrl
    typeAttributes: TypeAttributes

    def city(self):
        return self.typeAttributes.liveEntertainment.location.city

    def _date(self):
        return self.typeAttributes.liveEntertainment.startDate

    def _postal_code(self):
        return self.typeAttributes.liveEntertainment.location.postal_code

    def __str__(self):
        return f"name: {self.name} - desc: {self.description} - location: {self.typeAttributes.liveEntertainment.location.city}"


# from https://www.useragents.me
def get_common_user_agents():
    pass


def generate_markdown(events: list[LiveEvent]) -> None:
    events = sorted(events, key=lambda event: event._date())
    markdown = ["# Events"]
    for event in events:
        available_tickets = f" - ab {event.price}€" if event.inStock else " - sold out"
        item = f"- [{event.name}]({event.link}): {event.city()}: {event._date()}{available_tickets}"
        markdown.append(item)
    with open(config["markdown_path"], "w") as outfile:
        outfile.write("\n".join(markdown))


def run():
    events = []
    for artist in ARTISTS:
        events_of_artist = get_events_for_artist(artist)
        sleep(0.1)  # don't send too many requests in a row?
        if events_of_artist:
            events.extend(filter_events(get_events_for_artist(artist), artist))
        else:
            pass
            # TODO:[info] no events found for {aritst}
    generate_markdown(events)


def is_match(artist_name: str, event_name: str) -> bool:
    event_name = "".join(char for char in event_name if char.isalnum() or char == " ")
    names = artist_name.split()
    first_name, last_name = names[0], names[-1]
    pattern = r"{0}(?:\s+[A-Za-z]+)?\s+{1}".format(first_name, last_name)
    return bool(re.search(pattern, event_name, re.IGNORECASE))


def filter_events(events: list[LiveEvent], artist):
    if not CITIES:
        return [
            event
            for event in events
            if is_match(artist, event.name) or is_match(artist, event.description)
        ]
    else:
        cities = [city.lower() for city in CITIES]
        return [
            event
            for event in events
            if event.city().lower() in cities
            and (is_match(artist, event.name) or is_match(artist, event.description))
        ]


def get_events_for_artist(artist: str, retries: int = 3) -> list[LiveEvent]:
    payload = {key: value for key, value in config["queryParams"].items() if value}
    payload["search_term"] = artist
    response = requests.get(
        config["endpoint"], params=payload, headers=config["headers"], timeout=1.0
    )
    events = list()
    try:
        response.raise_for_status()
        data = response.json()
        products = data.get("products")
        for product in products:
            events.append(LiveEvent.model_validate(product))
    except ValidationError as err:
        # log validation error + message in the md
        print(err)
    except Timeout as t_out:
        if retries > 0:
            sleep(0.5)
            get_events_for_artist(artist, retries - 1)
        else:
            # TODO: log t_out
            pass
    except requests.RequestException as e:
        # TODO:log validation error + message in the md
        raise SystemExit(e)
    return events


if __name__ == "__main__":
    run()
