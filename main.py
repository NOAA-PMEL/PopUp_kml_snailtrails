'''
TODO:
    Needs to record all the data from stuff like this:
    https://eclipse.pmel.noaa.gov/rudics/POPS/0024/C0024_08_04_2021
'''


import requests
from lxml import html
import csv
import time
import calendar
from datetime import datetime

# user inputs
# start and stop times
start = 11
stop = 60
# only use the latest date?

latest_date_only = False

base_url = 'https://eclipse.pmel.noaa.gov/rudics/POPS/'
#export_file = 'popup_QC_check.csv'
now = datetime.now()
#export_file = 'popup_QC_check ' + now.strftime('%y%m%d') + '.csv'
export_file = 'popup_QC_check ' + now.strftime('%y%m%d') + '.csv'

start_time = calendar.timegm(time.strptime("20", '%y')) #starts time from January 1, 2020

# expected ranges for variables
err_range = {'EP':  {'low':  start_time, 'up':   calendar.timegm(time.gmtime())},
             'PD':  {'low':  0, 'up':   1.1},
             'P0':  {'low':  18, 'up':  35},
             'P1':  {'low':  18, 'up':  35},
             'BV':  {'low':  15.5, 'up': 30},
             'PR':  {'low':  300, 'up': 600}
             }

class PuF_data:
    def __init__(self, ID, set):
        self.ID = ID      #popup ID
        self.set = set    #dataset, a date
        self.gps_data = {}
        self.data = []

    def import_GPS(self, dstr):

        # GPS info
        gps_locs = {
            'DT':   0,    # GPS datetime
            'T':    3,     # time?
            'LAT':  4,   # latitude
            'LATD': 5,  # latitude dir
            'LON':  6,   # longitude
            'LOND': 7,  # longitude dir
            'Q':    8,     # quality metric
            'S':    9,     # satellites
            'H':    10,     # hours?
            'M':    11     # minutes?
        }

        d_units = dstr[:-2].split(',')

        loc_list = list(gps_locs.keys())

        for n in range(len(loc_list)):

            loc = loc_list[n]
            self.gps_data[loc] = d_units[n]

        return self.gps_data

    def import_data(self, dstr):

        #swich-case functions, called from data_decoding dict
        def epXX(hx):
            return str(int('0x' + str(hx), 0))

        def pdXX(hx):
            # dec = int('0x' + str(hx), 0)
            # return float(dec)/100
            value = int('0x' + str(hx), 16)
            if value & (1 << 15):
                value -= 1 << 16
            return value/100

        def pXX(hx):
            dec = int('0x' + str(hx), 0)
            return float(dec)/1000

        def bvXX(hx):
            return float(hx)/10

        def prXX(hx):
            return hx

        # data locations
        data_locs = {
            'EP': 0,  # epoch time
            'PD': 1,  # depth, should be ~0.53m
            'P0': 2,  # temperature sensor 0, depends on ambient, probably ~20-25
            'P1': 3,  # temperature sensor 1, depends on ambient, probably ~20-25
            'BV': 4,  # batter voltage, > 15.5
            'PR': 5   # vacuum, 300 < x < 600
        }

        data_decoding = {
            'EP': epXX,  # epoch time
            'PD': pdXX,  # depth, should be ~0.53m
            'P0': pXX,   # temperature sensor 0, depends on ambient, probably ~20-25
            'P1': pXX,   # temperature sensor 1, depends on ambient, probably ~20-25
            'BV': bvXX,  # batter voltage, > 15.5
            'PR': prXX   # vacuum, 300 < x < 600
        }

        d_units = dstr[:-2].split(',')
        loc_list = list(data_locs.keys())
        temp = {}

        for n in range(len(loc_list)):

            loc = loc_list[n]

            try:
                #self.data[loc] = data_decoding[loc](d_units[n])
                temp[loc] = data_decoding[loc](d_units[n])
            except:
                KeyError
                #self.data[loc] = ''
                temp[loc] = ''

            self.data.append(temp)

        return temp


def gen_url(base, start, stop):

    sets = {}

    for n in range(start, stop+1):

        r = requests.get(base + '//' + str(n).zfill(4) + '//')
        webpage = html.fromstring(r.content)
        links = webpage.xpath('//a/@href')

        for m in range(4, len(links)):

            if "POPS" in links[m]:
                continue

            set_name = str(n).zfill(4) + links[m]
            sets[set_name] = base + '/' + str(n).zfill(4) + '/' + links[m]

    return sets


if __name__ == '__main__':
    
    headers = ['PopUp', 'Set', 'Epoch time [EP]', 'Depth [PD]', 'Temp 1 [P0]', 'Temp 2 [P1]', 'Battery voltage [BV]', 'Pressure [PR]', 'Error flag']
    latest = str(start).zfill(4)


    datasets = gen_url(base_url, start, stop)
    set_names = list(datasets.keys())

    raw = {}
    for_export = []
    for_export_latest = []
    #set_n = 1

    for set in set_names:

        #set = set + '_' + str(set_n).zfill(4)
        #set_n = set_n + 1

        r = requests.get(datasets[set])
        content = str(r.content).split('\\n')

        raw[set] = PuF_data(set[:4], set)
        data_keys = {}

        for n in range(len(content)):

            line = content[n].split(',')

            if len(line[0]) == 20:
                raw[set].import_GPS(content[n])
            elif len(line[0]) == 8:
            # extract and decode other popup data
                raw[set].import_data(content[n])
            else:
                continue

        for data_set in list(raw[set].data):

            temp = [set[:4], set[4:]]
            err_col = ''

            for col in list(data_set.keys()):

                try:
                    in_range = err_range[col]['low'] < float(data_set[col]) < err_range[col]['up']
                except:
                    ValueError
                    in_range = False

                if not in_range:
                    err_col = err_col + ", " + col

                temp.append(data_set[col])
            temp.append(err_col)

            for_export.append(temp)

    last_line = []

    for line in for_export:

        if line[0] != latest:
            for_export_latest.append(last_line)

        latest = line[0]
        last_line = line

    for_export_latest.append(for_export[-1])

    with open(export_file, 'w', newline='') as f:
        
        cwriter = csv.writer(f)
        cwriter.writerow(headers)

        for row in for_export:

            cwriter.writerow(row)

    with open('latest ' + export_file, 'w', newline='') as f:

        cwriter = csv.writer(f)
        cwriter.writerow(headers)

        for row in for_export_latest:
            cwriter.writerow(row)









