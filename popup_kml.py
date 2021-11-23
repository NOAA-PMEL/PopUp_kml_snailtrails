'''
TODO:

'''


import requests
from lxml import html
import simplekml
import datetime
import pandas as pd
import matplotlib as mpl
import numpy as np

def gen_urls(base):
    '''
    Gets all the links from a provided url
    :param base: url
    :return: list of linked urls, the first few are erroneous and thus removed
    '''

    r = requests.get(base)
    webpage = html.fromstring(r.content)
    links = webpage.xpath('//a/@href')

    return links[5:]


def epXX(hx):
    '''
    Decodes epoch time
    :param hx:
    :return: string of epoch time
    '''

    return datetime.datetime.fromtimestamp(int('0x' + str(hx), 0))


def pXX(hx):
    '''
    Decodes temperature data
    :param hx:
    :return: float celcius temperature
    '''

    dec = int('0x' + str(hx), 0)
    return float(dec) / 1000


def colorFader(c1, c2, mix=0):
    '''
    :param c1: Starting color for gradient
    :param c2: Ending color for gradient
    :param mix: Float between 0-1, where the data sits on the gradient
    :return:
    '''

    c1 = np.array(mpl.colors.to_rgb(c1))
    c2 = np.array(mpl.colors.to_rgb(c2))

    return mpl.colors.to_hex((1 - mix)*c1 + mix*c2)

def get_rudics_data(url):
    '''
    collects data from a rudics database, requires the gen_urls function to follow links,
    Also requires specific if string sections for each desired data heading
    :param url: url of database
    :return: dict, with datetime as keys and list of data for items
    '''


    gps_data = {}
    temp_data = {}
    datasets = gen_urls(url)
    start = ''

    for set in datasets:

        date_format = "%Y-%m-%dT%H:%M:%SZ"
        cur_set = url + '//' + set
        # set_n = set_n + 1

        r = requests.get(cur_set)
        # content = str(r.content).split('\\n')
        content = str(r.content).split('%%')

        for sect in content:
            # Individual sections (ie 'GPS' or 'POPS') have to be added by hand.

            if 'GPS' in sect:

                block = sect.split('\\r\\n')

                for line in block:

                    if 'GNGGA' in line:
                        elems = line.split(',')
                        gps_data[datetime.datetime.strptime(elems[0], date_format)] = elems

            if 'POPS' in sect:

                block = sect.split('\\r\\n')

                for line in block:

                    if len(line) > 20:

                        elems = line.split(',')
                        temp_data[epXX(elems[0])] = [pXX(elems[2]), pXX(elems[3])]

    return gps_data, temp_data


def gen_kml(data, path):
    '''
    Takes a dict with data and write lat and lon into a .kml file
    Currently columns are magic numbers, hardcoded in here. Might need to change if this
    :param data: dataframe, with date as the index
    :param path: output file path for the .kml file
    :return:
    '''

    kml = simplekml.Kml()

    points = kml.newfolder(name='Points')
    lines = kml.newfolder(name='Color Line')

    lat0 = None
    lon0 = None

    for row in data.itertuples():

        if int(row[-1]) == 0:
            lat0 = row[1]
            lon0 = row[2]
            timestamp = row[0]
            continue

        ln = lines.newlinestring(name=row[-1],
                          coords=[(lon0 / -100, lat0 / 100),
                                  (row[2] / -100, row[1] / 100)],
                          altitudemode=simplekml.AltitudeMode.relativetoground)

        ln.linestyle.width = 3
        ln.timespan.begin = timestamp.isoformat() + 'Z'
        ln.timespan.end = row[0].isoformat() + 'Z'

        try:
             #cf = colorFader('blue', 'red', row[-3] / colorBase)
             cf = colorFader('blue', 'red', row[-2])
        except ValueError:

            if row[-2] > 1:
                cf = colorFader('blue', 'red', 1)
            elif row[-2] < 0:
                cf = colorFader('blue', 'red', 0)

        ln.style.linestyle.color = 'ff' + cf[5:7] + cf[3:5] + cf[1:3]

        name = str(row[-4])[:7] + '°'

        pnt = points.newpoint(name=name,
                           coords=[(row[2] / -100, row[1] / 100)]
                           )

        pnt.timestamp.when = row[0].isoformat() + 'Z'

        pnt.style.labelstyle.color = 'ff' + cf[5:7] + cf[3:5] + cf[1:3]
        pnt.style.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png'

        lat0 = row[1]
        lon0 = row[2]
        timestamp = row[0]

    kml.save(path + 'test.kml')


def date_inner_limits(set1, set2):
    '''
    Returns a date range where two data sets overlap
    :param set1:
    :param set2:
    :return: Start and end dates
    '''


    if set1.index[0] < set2.index[0]:
        start_date = set2.index[0]
    else:
        start_date = set1.index[0]

    if set1.index[-1] < set2.index[-1]:
        end_date = set1.index[-1]
    else:
        end_date = set2.index[-1]

    return start_date, end_date

if __name__ == "__main__":

    url = "http://eclipse.pmel.noaa.gov/rudics/POPS/0001/"
    path = 'D:\Data\PopUps\Snail trails\\'

    gps, temp = get_rudics_data(url)

    gps_df = pd.DataFrame(gps).transpose()
    gps_df.columns = ['DT', 'ID', 'T', 'LAT', 'LATD', 'LON', 'LOND', 'Q', 'S', 'H', 'M']
    gps_df = gps_df[['LAT', 'LON']].astype('float64')
    gps_df.drop(gps_df[gps_df['LAT'] < 4500].index, inplace=True, axis='rows')
    gps_df.drop(gps_df[gps_df['LON'] < 16000].index, inplace=True, axis='rows')

    temp_df = pd.DataFrame(temp).transpose()
    temp_df.columns = ['P0', 'P1']

    master = pd.concat([gps_df[['LAT', 'LON']], temp_df[['P0', 'P1']]], axis=1, sort=True)

    start_date, end_date = date_inner_limits(gps_df, temp_df)

    master = master[master.index > start_date]
    master = master[master.index < end_date]
    master = master.astype('float64')
    master.interpolate(method='time', inplace=True)
    master.dropna(inplace=True)
    master['PM'] = master[['P0', 'P1']].mean(axis='columns')
    master['P0N'] = (master['P0']-master['P0'].min())/(master['P0'].max() - master['P0'].min())
    master['no'] = list(range(0, len(master)))

    gen_kml(master, path)

