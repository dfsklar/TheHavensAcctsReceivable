# -*- coding: utf-8 -*-
"""
Created on Fri Jul 23 00:02:10 2021

This now supports both old-era (before each customer had a pass-through row) and
new era.

An old-era is recognized by the Reservation row having a CollectedTaxRate cell with "SYNTHESIZE*".

It will either say:
    SYNTHESIZE-GST
    or
    SYNTHESIZE-GST-ALBERTA


"""

import csv
import sys

# This is designed to handle CSVs that do NOT have explicit "Pass Through Tot" rows.
# This means we must ourselves calculate the portion of revenue which is GST-taxable.
# The way AirBNB has started doing this calc in the new era is by adding:
#    {Reservation row: Amount} + {Reservation row: Host Fee}

# How to map from USD to CAD?
# Each time we run this, we are dealing with a 3-month period.

# For this run, we are dealing with JAN-FEB-MAR of 2021.
# Let's just go with the middle of the period:
exchrate_midperiod = 1.26   # FEB 16 2021
exchrate = exchrate_midperiod


total_passthru_USD = 0.0

for monthkey in (1,2,3):
    strmonthkey = str(monthkey)
    filename = 'airbnb_{strmonthkey}_2021-{strmonthkey}_2021.csv'.format(**locals())
    with open(filename, mode='r') as csvfile:
        engine = csv.DictReader(csvfile)
        for row in engine:
            if row['Type'] == 'Pass Through Tot':
                total_passthru_USD += float(row['Amount'])
                
print(total_passthru_USD)

taxable_portion_USD = total_passthru_USD * 25.0


print('Revenue that AirBNB decided was the taxable portion: ')
print('    USD ' + str(taxable_portion_USD))
print('    CAD ' + str(taxable_portion_USD * exchrate))

print('------------------------')

print('ALBERTA tax collected by us on that airbnb-determined taxable portion: ')
print('    USD: ' + str(total_passthru_USD))
print('    CAD: ' + str(total_passthru_USD * exchrate))

print('------------------------')

print('GST amount on that airbnb-determined taxable portion: ')
print('    USD: ' + str(taxable_portion_USD * 0.05))
print('    CAD: ' + str(taxable_portion_USD * 0.05 * exchrate))





                

        