from datetime import datetime

import requests


def fetch_data_from_endpoint(url):
    token = datetime.utcnow().strftime('%Y%m%d')
    params = {
        'token': token
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        try:
            data = response.json()
            return data

        except ValueError as e:
            print(f'Error parsing JSON: {e}')
            return None
    else:
        print(f'Failed to get data. Status Code: {response.status_code}')
        return None
