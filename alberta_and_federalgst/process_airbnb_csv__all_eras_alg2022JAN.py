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

















# OK now let's deal with NOV of 2021
exchrate_endperiod = 1.281
exchrate = exchrate_endperiod


# OK now let's deal with DEC of 2021
exchrate_endperiod = 1.256
exchrate = exchrate_endperiod


# OK now let's deal with OCT of 2021
exchrate_endperiod = 1.240
exchrate = exchrate_endperiod


# OK now let's deal with SEP of 2021
exchrate_endperiod = 1.268
exchrate = exchrate_endperiod

# OK now let's deal with AUG of 2021
exchrate_endperiod = 1.254
exchrate = exchrate_endperiod

# OK now let's deal with JUL of 2021
exchrate_endperiod = 1.248
exchrate = exchrate_endperiod

# OK now let's deal with JUN of 2021
exchrate_endperiod = 1.24
exchrate = exchrate_endperiod

# OK now let's deal with MAY of 2021
exchrate_endperiod = 1.21
exchrate = exchrate_endperiod

# OK now let's deal with APR of 2021
exchrate_endperiod = 1.23
exchrate = exchrate_endperiod

# OK now let's deal with MAR of 2021
exchrate_endperiod = 1.26
exchrate = exchrate_endperiod

# OK now let's deal with FEB of 2021
exchrate_endperiod = 1.27
exchrate = exchrate_endperiod

# OK now let's deal with JAN of 2021
exchrate_endperiod = 1.28
exchrate = exchrate_endperiod






#----------------------------------------

total_passthru_4pct_USD = 0.0
total_passthru_5pct_USD = 0.0
total_passthru_9pct_USD = 0.0

total_poststay_adjustments = 0.0

total_amount_column = 0.0

total_hostfee = 0.0


for monthkey in [1]:
    strmonthkey = str(monthkey)
    print('--------------------------\n\n\nMONTH: {strmonthkey}\n\n'.format(**locals()))
    filename = 'airbnb_{strmonthkey}_2021-{strmonthkey}_2021.csv'.format(**locals())
    with open(filename, mode='r') as csvfile:
        engine = csv.DictReader(csvfile)
        for row in engine:
            if row['Amount']:
                amount = float(row['Amount'])
                total_amount_column += amount
                
                if 'Resolut' in row['Type']:
                    total_poststay_adjustments += amount
                    
                elif row['Type'] == 'Pass Through Tot':
                    passthru_rate = float(row['CollectedTaxRate'])
                    if passthru_rate == 0.04:
                        total_passthru_4pct_USD += amount
                    elif passthru_rate == 0.09:
                        total_passthru_9pct_USD += amount
                    else:
                        assert(False)
                    
                elif row['Type'] == 'Reservation':
                    if '(cancel' in row['Guest']:
                        # In this scenario, the guest cancelled "too late" and some of their
                        # funds are being passed to us.  AirBNB does not post a "pass thru" row
                        # and thus it must be assumed that the customer is refunded GST+Alberta.
                        # Thus, the amount in the "Amount" column is treated like a post-stay adj
                        # and considered to be not related to taxation.
                        # The host fee is NOT an expense in this situation since the amount column
                        # already is post-hostfee-reduction.
                        total_poststay_adjustments += amount
                    else:
                        total_hostfee += float(row['Host Fee'])
                        if 'SYNTH' in row['CollectedTaxRate']:
                            if 'ALB' in row['CollectedTaxRate']:
                                # OK so we need to collect both GST and ALBERTA
                                # So we reverse-engineer the taxes by carving them out from the total payout
                                #print(amount)
                                base_revenue = amount / 1.09
                                #print(base_revenue)
                                tax_amount = amount - base_revenue
                                #print(tax_amount)
                                total_passthru_9pct_USD += tax_amount
                            else:
                                base_revenue = amount / 1.05
                                #print(base_revenue)
                                tax_amount = amount - base_revenue
                                #print(tax_amount)
                                total_passthru_5pct_USD += tax_amount


#---------------------

total_nonresolution_amount = total_amount_column - total_poststay_adjustments
print('Total of amounts column that are neither "cancel" nor "resolution" ' + str(total_nonresolution_amount))

print('Total of post-stay adjustments (cancellation forfeits going to us + resolution cred/debits): ' + str(total_poststay_adjustments))


# Definition: the "pre-resolution base revenue" is the taxable base before taking into account
# any resolution adjustments either pos or neg.
# Abbreviation:  prbaserev
#

reverse_engineered_baserev = \
    total_passthru_4pct_USD * 25.0 \
    + \
    total_passthru_5pct_USD * 20.0 \
    + \
    total_passthru_9pct_USD * (100.0 / 9.0)
# Note that the reverse-engineered base revenue includes the "host fee" which actually
# reduces our "take-home payout".

# We are not going to add in the poststay adjustments:

total_taxable_and_taxcollected = \
    reverse_engineered_baserev + \
        total_passthru_4pct_USD + total_passthru_5pct_USD + total_passthru_9pct_USD


if total_passthru_5pct_USD > 0.01:
    # OLD ERA!  There is no Alberta relevancy in this era!
    era = 'OLD'
    prbaserev_USD = total_taxable_and_taxcollected / 1.05  # 5% GST
else:
    era = 'NEW'
    prbaserev_USD = total_taxable_and_taxcollected / 1.09  # 5% GST amd 4% Alberta


# This also includes the host fee that will be removed from our final payout


print('\nTotal of base revenue + tax: ' + str(total_taxable_and_taxcollected))
print('The above number ignores resolution adjustments (pos or neg) but includes host fees.')


print('------------------------')

print('Revenue that AirBNB decided was the taxable base (includes hostfee that will be lost later): ')
print('    USD ' + str(prbaserev_USD))
print('    CAD ' + str(prbaserev_USD * exchrate))

print('------------------------')

print('ALBERTA tax to be remitted:')
if era == 'OLD':
    print(' Z E R O')
else:
    print('    USD: ' + str(prbaserev_USD*0.04))
    print('    CAD: ' + str(prbaserev_USD*0.04 * exchrate))

print('------------------------')

print('GST to be remitted: ')
print('    USD: ' + str(prbaserev_USD * 0.05))
print('    CAD: ' + str(prbaserev_USD * 0.05 * exchrate))

print('------------------------')

print('TOTAL HOST FEES (you must declare as an expense): ')
print('    USD: ' + str(total_hostfee))
print('    CAD: ' + str(total_hostfee * exchrate))


print('------------------------')

print('Post-Stay adjustments income: ')
print('    USD: ' + str(total_poststay_adjustments))
print('    CAD: ' + str(total_poststay_adjustments * exchrate))

