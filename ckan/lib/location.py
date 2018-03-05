# encoding: utf-8

'''Module to add latitude and longitude at the end of csv file containing adresses

    It takes as parameter a data_dict obtained from a form filled in the front end during the creation of a new resource.
    This data_dict contains especially 4 fields : address, addition, city and zipcode. Their values are an index (integer).

    When a csv file is imported, its first line is the name of each column.
    When this file is read by the csv reader, each line is converted in a dict with the names of each column
    (fieldnames) as keys and the values of this line as values.
    The index from the data_dict is the index of each column in the file minus one
    (as the numbering starts at 1 for humans and 0 for python).
    This index gets the name of the field from fieldnames. This name is then used as the key in each line
    to get the desired value for the address, city and zipcode.
    Finally, a gouv api is called to get the coordinates linked to this address and the result is added to the original file.
'''

import collections
import logging
import requests
import csv
import os
from multiprocessing.pool import ThreadPool

log = logging.getLogger(__name__)
Coordinates = collections.namedtuple('Coordinates', 'latitude longitude')
Address = collections.namedtuple('Address', 'street city zipcode')

BASE_URL = 'https://api-adresse.data.gouv.fr/search/?q='
pool = ThreadPool(processes=10)


def geocode(address):
    '''Manage the requests to get the coordinates
    :param address:
    :type address: namedtuple
    :returns: the coordinates
    :rtype: dictionary
    '''
    if not isinstance(address, Address):
        raise ValueError('Wrong address type')

    url = BASE_URL + address.street + ' ' + address.city + '&postcode=' + address.zipcode
    coordinates = make_request(url)

    # retry by simplifying the request parameters
    if coordinates.longitude is None or coordinates.latitude is None:
        url = BASE_URL + address.street + '&postcode=' + address.zipcode
        coordinates = make_request(url)

    log.info('geocode coordinates {} : {}'.format(address, coordinates))
    return coordinates


def make_request(url):
    '''Make the request to get the latitude and longitude

    :param url:
    :type url: string
    :returns: the coordinates
    :rtype: dictionnary
    '''
    log.info(url)
    headers = {"User-Agent": "Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/25.0"}
    coordinates = Coordinates(None, None)

    try:
        get = requests.get(url=url, headers=headers, timeout=2)
        if get.status_code != 200:
            raise requests.ConnectionError()
    except Exception as err:
        log.error('geocode {0} failed: {1}'.format(url, err))
    else:
        data = get.json()
        # Get latitude and longitude from the json response
        if data['features']:
            coordinates = Coordinates(data['features'][0]['geometry']['coordinates'][1],
                                      data['features'][0]['geometry']['coordinates'][0])
    return coordinates


def get_field_name(column_idx, column_count, fieldnames):
    idx = int(column_idx) if column_idx.isdigit() else 0
    return fieldnames[idx - 1] if column_count > idx > 0 else None


def geores(file, data_dict):
    '''
    :param file:
    :type file: filename
    :param data_dict:
    :type data_dict: dictionnary
    :return:
    '''
    # If geolocation parameters are not specified, return
    if data_dict.get('address', '') == data_dict.get('addition', '') == data_dict.get('zipcode', '') == data_dict.get(
            'city', '') == '':
        return

    # If file is not csv, empty or not found do nothing ...
    type = data_dict.get('mimetype', '')
    if type != 'text/csv' or not os.path.exists(file) or os.path.getsize(file) <= 0:
        log.error('Wrong type or file not found')
        return

    with open(file, 'r') as csvin:
        try:
            # extra protection here to avoid crashing the whole server
            csvreader = csv.DictReader(csvin, delimiter=';')
        except Exception as err:
            log.error('An error happened while reading the file : {0}, file will only be saved'.format(err))
            return

        records = list(csvreader)
        log.info('Length of file : {}'.format(len(records)))
        log.debug('Retrieve {0} records'.format(len(records)))
        col_count = len(csvreader.fieldnames)

        # Get the name of the fields given by the user from fieldnames list
        # could be uppercase or camelcase?
        if csvreader.fieldnames[-2:] == ['latitude', 'longitude']:
            fieldnames = csvreader.fieldnames
        else:
            fieldnames = csvreader.fieldnames + ['latitude', 'longitude']

        # Get the name of the studied fields
        col_street_name = get_field_name(data_dict.get('address', '0'),
                                         col_count,
                                         fieldnames)

        col_street_bis_name = get_field_name(data_dict.get('addition', '0'),
                                             col_count,
                                             fieldnames)

        col_zipcode_name = get_field_name(data_dict.get('zipcode', '0'),
                                          col_count,
                                          fieldnames)

        col_city_name = get_field_name(data_dict.get('city', '0'),
                                       col_count,
                                       fieldnames)

        if col_street_name is None and \
           col_street_bis_name is None and \
           col_zipcode_name is None and \
           col_city_name is None:
            log.warning('Wrong column indexes, file will only be saved')
            return

    addresses = []

    for record in records:
        # Get the address, zipcode and city from the record
        street = record.get(col_street_name, '') or ''
        street_bis = record.get(col_street_bis_name, '') or ''
        zipcode = record.get(col_zipcode_name, '') or ''
        city = record.get(col_city_name, '') or ''
        addresses.append(Address(street + ' ' + street_bis, city, zipcode))
    log.info('Length of addresses : {}'.format(len(addresses)))

    result = pool.imap(geocode, addresses)

    with open(file, 'wb') as csvout:
        csvwriter = csv.DictWriter(csvout, fieldnames, delimiter=';')
        csvwriter.writeheader()

        for record, coordinates in zip(records, result):
            log.info('Wrinting in file : {0} and {1}'.format(record, coordinates))
            # Get the coordinates and add them to the record
            if coordinates.latitude != None and coordinates.longitude != None:
                csvwriter.writerow(dict(record, latitude=coordinates.latitude, longitude=coordinates.longitude))
            else:
                csvwriter.writerow(dict(record))
