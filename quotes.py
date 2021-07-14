#!/usr/local/bin/python3
import json
import requests
from collections import OrderedDict
from pathlib import Path
import random
import logging

HOME_DIR = "/Users/sahuja4/Dropbox (Facebook)/Second Brain/Scripts"
QUOTES_FILE = "quotes.json"
STOIC_API_GET_URL = "https://stoicquotesapi.com/v1/api/quotes"
logger = logging.getLogger(__name__)

logger.setLevel(level=logging.INFO)
log_format = "%(asctime)s:%(name)s:%(levelname)s:%(message)s"
logging.basicConfig(format=log_format)


class QuotesGetter:
    def __init__(self):
        self.quotes = {}
        self.error = None

    def get_a_random_quote(self):
        self._get_quotes()
        if self.error or not self.quotes or len(self.quotes) == 0:
            return None
        # pick a random day
        day = random.choice(list(self.quotes.keys()))
        return random.choice(list(self.quotes[day]))

    def _get_quotes(self):
        quotes_file = f"{HOME_DIR}/{QUOTES_FILE}"
        self.quotes, error = get_quotes_from_file(quotes_file)
        if error or len(self.quotes) == 0:
            quotes, error = QuotesGetterViaApi().get_quotes()
            if error:
                logger.error(f"Issues in getting quotes from api {error}")
                self.error = error
                return
            self.quotes = quotes
            write_out_file = open(quotes_file, "w+")
            error = marshal_data_and_write_to_file(quotes, write_out_file)
            if error:
                logger.error(f"Issues in marshalling data to file {error}")
                self.error = error
                return


def get_quotes_from_file(file_absolute_path: str):
    quotes_file = Path(file_absolute_path)
    logging.info(f"Opening file at {quotes_file}")
    quotes_file.touch(exist_ok=True)
    unmarshalled_data = ""
    error = None
    # create a file if it doesn't already exist
    try:
        with open(quotes_file, "r+") as f:
            unmarshalled_data, error = unmarshal_data(f.read())
            if error:
                raise Exception(f"Problem in unmarshalling data {error}")
    except Exception as e:
        error = e
    return unmarshalled_data, error


def marshal_data_and_write_to_file(data_dict, file_obj):
    error = None

    try:
        json.dump(data_dict, file_obj)
    except Exception as e:
        error = e
    return error


def unmarshal_data(data: str):
    error = None
    data = None
    try:
        data = json.loads(data, object_pairs_hook=OrderedDict)
    except Exception as e:
        error = e
    return data, error


class QuotesGetterViaApi:
    def __init__(self):
        self.quotes = OrderedDict()
        self.error = None

    def get_quotes(self):
        self._get_quotes_from_stoic()
        return self.quotes, self.error

    def _get_quotes_from_stoic(self):
        try:
            # 6 is the number of pages in the stoic Api, so that gives us 60 quotes
            for i in range(7):
                resp = requests.get(f"{STOIC_API_GET_URL}?page={i}")
                if resp.status_code != 200:
                    # This means something went wrong.
                    raise IOError('GET /tasks/ {}'.format(resp.status_code))
                self.quotes[str(i)] = self._extract_data_from_json(resp.json())
        except Exception as e:
            self.error = e

    def _extract_data_from_json(self, response):
        quotes_author = []
        try:
            quotes_author = [(q["body"], q["author"])
                             for q in response["data"]]
        except Exception as e:
            self.error = e

        return quotes_author


if __name__ == "__main__":
    print(QuotesGetter().get_a_random_quote())
