import requests
import csv
from typing import List, Dict
from functools import reduce
from oauthlib.oauth2 import BackendApplicationClient

from requests_oauthlib import OAuth2Session
from .auth import Token 

def question_id_to_header(question_id:str):
    if question_id == "fas":
        return "Fedora Account Services (FAS)"
    elif question_id == "matrix":
        return "Matrix ID"
    
    return ""

class Pretix:

    def __init__(self, instance_url, client_id, client_secret, redirect_uri):
        self._instance_url = instance_url
        self._client_secret = client_secret
        self.client = BackendApplicationClient(client_id=client_id)
        # most providers will ask you for extra credentials to be passed along
        # when refreshing tokens, usually for authentication purposes.
        # extra = {
        #     'client_id': client_id,
        #     'client_secret': r'potato',
        # }
        self.oauth = OAuth2Session(
            client=client,
            # token=token,
            auto_refresh_url=self.token_url,
            token_updater=self._update_token)#auto_refresh_kwargs=extra,
    
    def test_auth(self):
        # test the auth
        r = self.oauth.get(self.test_url)
        r.raise_for_status()
        
    @property
    def _has_token(self):
        return self._token is not None and self._token != ""

    @property
    def _has_refresh_token(self):
        return self._refresh_token is not None and self._refresh_token != ""

    @property
    def oauth_url(self):
        return self.get_oauth_url()

    @property
    def token_url(self):
        return self.base_url + "/oauth/token"

    @property
    def test_url(self):
        return self.base_url + "/organizers/(organizer)/events"

    def _update_token(self, token:str):
        """in-memory token storage

        Args:
            token (str): the token to store
        """
        self._token = Token.from_str(token)


    def get_auth_url(self, write=False):
        authorization_url, state = oauth.authorization_url(
            self.base_url + "/oauth/authorize"
        )
        # client_id
        # response_type
        # scope
        # redirect_uri
        
        # TODO: figure out what is needed to get write access - this isnt needed right now though
        # read_write = "read" if not write else ""

        # return self.base_url + f"/oauth/authorize?client_id={self.client_id}&response_type=code&scope=read&redirect_uri={self.redirect_uri}"
        return authorization_url

    def set_token_from_auth_callback(self, authorization_response:str):
        """complete the auth process by using the response from the oauth process to fetch a token

        Args:
            authorization_response (str): the URL of the auth response - it should contain the code value
        """
        token = oauth.fetch_token(
            self.token_url,
            authorization_response=authorization_response,
            client_secret=self._client_secret
            )
        self._update_token(token)
        return

    @property
    def base_url(self):
        return self._instance_url + "/api/v1"

    def listen(self):
        """spin up a web server to listen on a particular IP and port for the redirect code
        """
        pass

    def fetch_data(self, organizer, event) -> dict:
        url = self.base_url + "/organizers/{organizer}/events/{event}/orders/"

        data = []

        while url:
            response = self.oauth.get(url)
            response.raise_for_status()
            json_response = response.json()
            data.extend(json_response.get('results', []))
            url = json_response.get('next')
        return data

    def extract_answers(self, schema: dict) -> List[dict]:
        def reducer(entries: Dict[str, dict], result: dict) -> Dict[str, dict]:
            for position in result.get('positions', []):
                ticket_id = position['order']
                if not entries.get(ticket_id):
                    entries[ticket_id] = {
                        'Order code': ticket_id,
                        'Email': result.get('email', ''),
                        "Order datetime": result.get("datetime", ''),
                        "Pseudonymization ID": position.get("pseudonymization_id", ''),
                        "Fedora Account Services (FAS)": '',
                        "Matrix ID": '',
                        "Invoice address name": result.get('invoice_address', {}).get('name', ''),
                    }
                for answer in position.get('answers', []):
                    if answer['question_identifier'] in {'matrix', 'fas'}:
                        entries[ticket_id][question_id_to_header(answer['question_identifier'])] = answer['answer']  # noqa: E501
            return entries

        reduced_results = reduce(reducer, schema, {})
        return list(reduced_results.values())


    def write_to_csv(self, entries: List[dict], file_name: str, display: bool = False) -> None:  # noqa: E501
        fieldnames = entries[0].keys()
        with open(file_name, mode='w+', newline='') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            for entry in entries:
                writer.writerow(entry)

            if not display:
                return

            csv_file.flush()
            csv_file.seek(0)
            print(csv_file.read())

    def filter_dict(self, old_dict, your_keys):
        """filters a dictionary so it only contains the specified keys
        accomplishes this by constructing a new dictionary
        """
        return { your_key: old_dict[your_key] for your_key in your_keys }

    
    def csv_to_data(self, csv_file:str) -> list[dict]:
        """_summary_

        Args:
            csv_file (str): the input filename to process

        Returns:
            list[dict]: the csv data in dict format for further processing
        """
        
        with open(csv_file) as csvfile:
            reader = csv.DictReader(csvfile)
            return list(reader)

    def cleanup_csv_for_humans(self, csv_data:list[dict], filter_keys=["Order code", "Email", "Order date", "Order time", "Pseudonymization ID", "Fedora Account Services (FAS)", "Matrix ID", "Invoice address name"]) -> list[dict]:
        """Takes in a CSV data (dict-formatted) and returns dict-formatted data with unused columns removed

        Args:
            csv_data (list[dict]): the input csv data to process

        Returns:
            list[dict]: the data with unused columns removed
        """
        return [filter_dict(d, filter_keys) for d in csv_data]
    

    def filter_processed_data(self, csv_data:list[dict], processed_csv_data:list[dict], filter_key:str="Order code") -> list[dict]:
        """filters csv data to remove data thats already been processed


        Args:
            csv_data (list[dict]): the input csv data to process
            processed_csv_data (list[dict]): the input csv data containing processed records to filter out
        
        Returns:
            list[dict]: the filtered version of the initial data with already-processed rows removed
        """
        
        processed_ids = set([ r[filter_key] for r in processed_csv_data])

        return list(filter(lambda d: d[filter_key] not in processed_ids, csv_data))
