# encoding: utf-8

'''Module to add latitude and longitude at the end of csv file containing adresses'''

import collections
import logging
import requests
import csv

log = logging.getLogger(__name__)
Coordinates = collections.namedtuple('Coordinates', 'latitude longitude')
BASE_URL = 'https://api-adresse.data.gouv.fr/search/?q='


def geocode(address, zipcode, city):
    '''Manage the requests to get the coordinates

    :param address:
    :type address: string
    :param zipcode:
    :type zipcode: string
    :param city:
    :type city: string
    :returns: the coordinates
    :rtype: dictionary
    '''
    headers = {"User-Agent": "Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/25.0"}

    url1 = BASE_URL + address + ' ' + city + '&postcode=' + zipcode
    url2 = BASE_URL + address + ' ' + city
    url3 = BASE_URL + city

    coordinates = make_request(url1, headers)
    if not coordinates:
        coordinates = make_request(url2, headers)
    if not coordinates:
        coordinates = make_request(url3, headers)
    if not coordinates:
        coordinates = Coordinates(None, None)
    return coordinates


def make_request(url, headers):
    '''Make the request to get the latitude and longitude

    :param url:
    :type url: string
    :param headers:
    :type headers: dictionary
    :returns: the coordinates
    :rtype: dictionnary
    '''

    log.info(url)
    try:
        get = requests.get(url=url, headers=headers)
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
    return None


def geores(file, data_dict):
    """

    :param data_dict:
    :type data_dict: dictionnary
    :return:
    """
    # If geolocation parameters are not specified, return
    if data_dict['address'] == data_dict['addition'] == data_dict['zipcode'] == data_dict['city'] == '':
        return

    # Check the input data : columns numbers must be integers
    try:
        addressindex = int(data_dict['address'])
        log.debug(addressindex)
    except ValueError:
        addressindex = None
    try:
        addressindex2 = int(data_dict['addition'])
        log.debug(addressindex2)
    except ValueError:
        addressindex2 = None
    try:
        zipcodeindex = int(data_dict['zipcode'])
        log.debug(zipcodeindex)
    except ValueError:
        zipcodeindex = None
    try:
        cityindex = int(data_dict['city'])
        log.debug(cityindex)
    except ValueError:
        cityindex = None

    with open(file, 'r') as csvfile:
        csvreader = csv.DictReader(csvfile, delimiter=';')
        lines = list(csvreader)
        log.debug('Retrieve {0} lines'.format(len(lines)))

        # Get the name of the fields given by the user from fieldnames list
        if csvreader.fieldnames[-2:] == ['latitude', 'longitude']:
            fieldnames = csvreader.fieldnames
        else:
            fieldnames = csvreader.fieldnames + ['latitude', 'longitude']
        addressname = fieldnames[addressindex - 1] if addressindex else None
        addressname2 = fieldnames[addressindex2 - 1] if addressindex2 else None
        zipcodename = fieldnames[zipcodeindex - 1] if zipcodeindex else None
        cityname = fieldnames[cityindex - 1] if cityindex else None

        if addressname:
            log.debug(addressname)
        if addressname2:
            log.debug(addressname2)
        if zipcodename:
            log.debug(zipcodename)
        if cityname:
            log.debug(cityname)

    with open(file, 'w') as csvfile:
        csvwriter = csv.DictWriter(csvfile, fieldnames, delimiter=';')
        csvwriter.writeheader()

        for line in lines:
            # Get the addrress, zipcode and city from the line
            address = line[addressname] if addressname else ''
            address2 = line[addressname2] if addressname2 else ''
            zipcode = line[zipcodename] if zipcodename else ''
            city = line[cityname] if cityname else ''
            log.debug(address + ', ' + address2 + ', ' + zipcode + ', ' + city)

            coordinates = geocode(address + ' ' + address2, zipcode, city)
            if coordinates.latitude != None and coordinates.longitude != None:
                csvwriter.writerow(dict(line, latitude=coordinates.latitude, longitude=coordinates.longitude))
            else:
                csvwriter.writerow(dict(line))
