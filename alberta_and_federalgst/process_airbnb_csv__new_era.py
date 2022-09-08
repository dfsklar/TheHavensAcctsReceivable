# -*- coding: utf-8 -*-
"""
Created on Fri Jul 23 00:02:10 2021

COMMITTED TO GITHUB:  AUG 07 about 10pm

This now supports both old-era (before each customer had a pass-through row) and
new era.

An old-era is recognized by the Reservation row having a CollectedTaxRate cell with "SYNTHESIZE*".

It will either say:
    SYNTHESIZE-GST
    or
    SYNTHESIZE-GST-ALBERTA

@author: sklar
"""

import csv
import sys

# How AirBNB has been determining the "taxable revenue":
#    {Reservation row: Amount} + {Reservation row: Host Fee}

# How to map from USD to CAD?
# Each time we run this, we are dealing with a 3-month period.

# For this run, we are dealing with APR+MAY+JUN of 2021.
# ^^^ Overkill?  Let's just go with the middle of the period:
exchrate_midperiod = 1.21
exchrate = exchrate_midperiod



# OK now let's deal with JUL of 2021
#exchrate_endperiod = 1.248
#exchrate = exchrate_endperiod


# OK now let's deal with AUG of 2021
#exchrate_endperiod = 1.254
#exchrate = exchrate_endperiod


# OK now let's deal with SEP of 2021
#exchrate_endperiod = 1.268
#exchrate = exchrate_endperiod


# OK now let's deal with OCT of 2021
#exchrate_endperiod = 1.240
#exchrate = exchrate_endperiod


# OK now let's deal with NOV of 2021
exchrate_endperiod = 1.281
exchrate = exchrate_endperiod


# OK now let's deal with DEC of 2021
exchrate_endperiod = 1.256
exchrate = exchrate_endperiod



total_passthru_4pct_USD = 0.0
total_passthru_9pct_USD = 0.0

total_oldera_payouts = 0.0
total_newera_payouts = 0.0



for monthkey in [12]:
    strmonthkey = str(monthkey)
    filename = 'airbnb_{strmonthkey}_2021-{strmonthkey}_2021.csv'.format(**locals())
    with open(filename, mode='r') as csvfile:
        engine = csv.DictReader(csvfile)
        for row in engine:
            if row['Type'] == 'Pass Through Tot':
                passthru_rate = float(row['CollectedTaxRate'])
                if passthru_rate == 0.04:
                    total_passthru_4pct_USD += float(row['Amount'])
                elif passthru_rate == 0.09:
                    total_passthru_9pct_USD += float(row['Amount'])
                else:
                    assert(False)
            if row['Type'] == 'Payout-OldEra':
                total_oldera_payouts += float(row['Paid Out'])
            if row['Type'] == 'Payout':
                total_newera_payouts += float(row['Paid Out'])
                

total_alleras_payouts = total_oldera_payouts + total_newera_payouts
base_income_oldcalctechnique = (total_oldera_payouts/1.05) + (total_newera_payouts/1.09)
print('Base revenue using my simple start-from-payouts technique:')
print('   USD: ' + str(base_income_oldcalctechnique))
print('   CAD: ' + str(base_income_oldcalctechnique * exchrate))
print('------------------------')
print('GST using my simple start-from-payouts technique:')
print('   USD: ' + str(base_income_oldcalctechnique*0.05))
print('   CAD: ' + str(base_income_oldcalctechnique*0.05 * exchrate))
print('------------------------')
print('Alberta using my simple start-from-payouts technique:')
print('   USD: ' + str((total_newera_payouts/1.09)*0.04))
print('   CAD: ' + str((total_newera_payouts/1.09)*0.04 * exchrate))
print('\n\n\n')

# I DO NOT BELIEVE I HAVE BEEN USING THE "start from payouts" SYSTEM ^^^^^^

# I BELIEVE I HAVE BEEN GOING WITH A SYSTEM THAT DERIVES EVERYTHING FROM THE passthru ROWS.
# All other rows are ignored!

taxable_portion_USD = \
    total_passthru_4pct_USD * 25.0 \
    + \
    total_passthru_9pct_USD * (100.0 / 9.0)
    
total_taxable_and_taxcollected = taxable_portion_USD + total_passthru_4pct_USD + total_passthru_9pct_USD  # Think of this as being 100%+5%+4% 
total_taxableincome_newera_USD = total_taxable_and_taxcollected / 1.09  # 5% GST amd 4% Alberta
print(total_taxable_and_taxcollected)

total_taxableincome_oldera = total_oldera_payouts/1.05
taxable_both_eras_USD = total_taxableincome_newera_USD + total_taxableincome_oldera



print('Revenue that AirBNB decided was the taxable portion (new era): ')
print('    USD ' + str(total_taxableincome_newera_USD))
print('    CAD ' + str(total_taxableincome_newera_USD * exchrate))
print('Revenue that AirBNB decided was the taxable portion (both eras): ')
print('    USD ' + str(taxable_both_eras_USD))
print('    CAD ' + str(taxable_both_eras_USD * exchrate))

print('------------------------')

print('ALBERTA tax collected by us on the new-era taxable income:')
print('    USD: ' + str(total_taxableincome_newera_USD*0.04))
print('    CAD: ' + str(total_taxableincome_newera_USD*0.04 * exchrate))

print('------------------------')

print('GST amount on the both-eras taxable portion: ')
print('    USD: ' + str(taxable_both_eras_USD * 0.05))
print('    CAD: ' + str(taxable_both_eras_USD * 0.05 * exchrate))
