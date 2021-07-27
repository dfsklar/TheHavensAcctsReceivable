# -*- coding: utf-8 -*-
"""
Created on Fri Jul 23 00:02:10 2021

@author: sklar
"""

import csv
import sys

# How to map from USD to CAD?
# Each time we run this, we are dealing with a 3-month period.

# For this run, we are dealing with APR+MAY+JUN of 2021.
# Why not take the approach of averaging "start APR" + "mid-MAY" + "end of JUN" as the exchange rate to use.

exchrate_midperiod = (1.256 + 1.21 + 1.239) / 3.0
exchrate_midperiod = 1.21


total_passthru = 0.0

for monthkey in (4,5,6):
    strmonthkey = str(monthkey)
    filename = 'airbnb_{strmonthkey}_2021-{strmonthkey}_2021.csv'.format(**locals())
    with open(filename, mode='r') as csvfile:
        engine = csv.DictReader(csvfile)
        for row in engine:
            if row['Type'] == 'Pass Through Tot':
                total_passthru += float(row['Amount'])
                
print(total_passthru)

print('Revenue that AirBNB decided was the taxable portion: ' + str(total_passthru * 25.0) + ' USD')

print('   ... that amount in CAD: ' + str(total_passthru * 25.0 * exchrate_midperiod)
