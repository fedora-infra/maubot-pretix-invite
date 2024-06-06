import requests
import csv
from typing import List, Dict
from functools import reduce


def question_id_to_header(question_id:str):
    if question_id == "fas":
        return "Fedora Account Services (FAS)"
    elif question_id == "matrix":
        return "Matrix ID"
    
    return ""

class Pretix:

    def __init__(self, instance_url, token):
        self._instance_url = instance_url
        self._token = token

    @property
    def base_url(self):
        return self._instance_url + "/api/v1"

    def fetch_data(self, organizer, event) -> dict:
        url = self.base_url + "/organizers/{organizer}/events/{event}/orders/"

        headers = {
            "Authorization": f"Bearer {self._token}"
        }
        data = []

        while url:
            response = requests.get(url, headers=headers)
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
