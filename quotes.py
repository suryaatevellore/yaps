#!/usr/local/bin/python3
import json
import requests
from collections import OrderedDict
from pathlib import Path, PosixPath
import random
import logging
from typing import Dict, List, TextIO, Tuple

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

    def get_a_random_quote(self) -> Tuple[str, str]:
        self._get_quotes()
        if self.error or not self.quotes or len(self.quotes) == 0:
            return None
        # pick a random day
        day = random.choice(list(self.quotes.keys()))
        chosen_quote = random.choice(list(self.quotes[day]))
        logger.info(f"Chosen quote : {chosen_quote}")
        return chosen_quote

    def _get_quotes(self) -> Dict[str, List[Tuple[str, str]]]:
        quotes_file = f"{HOME_DIR}/{QUOTES_FILE}"
        quotes_file = Path(quotes_file)
        quotes_file.touch(exist_ok=True)
        self.quotes, error = get_quotes_from_file(quotes_file)
        if error or not self.quotes or len(self.quotes) == 0:
            quotes, error = QuotesGetterViaApi().get_quotes()
            if error:
                logger.error(f"Issues in getting quotes from api {error}")
                self.error = error
                return
            self.quotes = quotes
            write_out_file = open(quotes_file, "a+")
            error = marshal_data_and_write_to_file(quotes, write_out_file)
            if error:
                logger.error(f"Issues in marshalling data to file {error}")
                self.error = error
                return


def get_quotes_from_file(quotes_file: PosixPath):
    logger.info(f"getting quotes from {quotes_file}")
    unmarshalled_data = ""
    error = None
    # create a file if it doesn't already exist
    try:
        with open(quotes_file, "r+") as f:
            file_data = f.read()
            unmarshalled_data, error = unmarshal_data(file_data)
            logger.info(
                f"Read {len(unmarshalled_data)} bytes of data from file")
            if error:
                raise Exception(f"Problem in unmarshalling data {error}")
    except Exception as e:
        error = e
    return unmarshalled_data, error


def marshal_data_and_write_to_file(data_dict: Dict[str, List[Tuple[str, str]]],
                                   file_obj: TextIO):
    error = None

    try:
        json.dump(data_dict, file_obj)
    except Exception as e:
        error = e
    return error


def unmarshal_data(data: str):
    error = None
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
            # 6 is the number of pages in the stoic Api, so that gives us 60
            # quotes
            logging.info("Getting quotes via stoicism api")
            for i in range(7):
                resp = requests.get(f"{STOIC_API_GET_URL}?page={i}")
                if resp.status_code != 200:
                    # This means something went wrong.
                    raise IOError('GET /tasks/ {}'.format(resp.status_code))
                self.quotes[str(i)] = self._extract_data_from_json(resp.json())
        except Exception as e:
            self.error = e

    def _extract_data_from_json(self, response):
        quotes_with_author = []
        try:
            quotes_with_author = [(q["body"], q["author"])
                                  for q in response["data"]]
        except Exception as e:
            self.error = e

        return quotes_with_author


if __name__ == "__main__":
    logger.setLevel(level=logging.INFO)
    log_format = "%(asctime)s:%(name)s:%(levelname)s:%(message)s"
    logging.basicConfig(format=log_format)
    print(QuotesGetter().get_a_random_quote())
