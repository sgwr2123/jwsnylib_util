#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys

import requests
import json
import time
import pprint
import codecs
import csv
import re
import xmltodict

import toshoutil

from toshoutil import debug_print
from toshoutil import open_csv

toshoutil.debug_level = 0

#=============================================================================
# convert SPro "added" date to libib format

def conv_date(x):
    r = re.sub('\/', '-', x)
    debug_print(2, 'conv_date |%s| -> |%s|' % (x, r))
    return r


#=============================================================================
# convert spro-based book info to libib inport format

def conv_book_info(row):
    isbn = toshoutil.normalize_isbn(row[5])
    added = conv_date(row[7])
    spro_id = row[6]
    ddc = row[17]
    lcc = row[19]

    r = [ isbn, added, spro_id, ddc, lcc]

    return r

#=============================================================================
# Read the input book list pre-processed by blist_lookup_isbn.py
# Produces 3 output booklist for Libib import (intended for different collections)
# main: The books with successful ISBN lookup and verified strict match on title
# title_unmach: Those with successful ISBN lookup but got title mismatch (likely small difference)
# lookup_fail: Those with ISBN lookup failure

def conv_blist(csvr, csvw_main, csvw_title_unmatch, csvw_lookup_fail):

    lno = 0
    title_row = ['ean_isbn13', 'added', 'call_number', 'ddc', 'lcc' ]

    for row in csvr:
        lno += 1

        if lno == 1: # skip the first line
            # Do emit the title lines for all 3 output book lists
            csvw_main.writerow(title_row)
            csvw_title_unmatch.writerow(title_row)
            csvw_lookup_fail.writerow(title_row)
            continue

        rout = conv_book_info(row)

        isbn_pcheck = row[0]
        isbn_lookup = row[2]

        if isbn_pcheck == 'NO_ISBN':  # Books w/o/ ISBN. Skip
            continue

        if isbn_pcheck == 'ISBN_NOT_UNIQUE': # books with non-unique ISBN, skip
            continue

        if isbn_lookup == 'NDL_HTTP_ERROR': # Those that got HTTP error for NDL search. Skip for now.
            continue

        # Pre-check passed. This book can be added in one of the 3 output list.

        if isbn_lookup == 'NDL_ISBN_NOT_FOUND': # ISBN not found both in OpenBD and NDL
            csvw_lookup_fail.writerow(rout)
            continue

        if (isbn_lookup != 'ISBN_OK') and (isbn_lookup != 'NDL_ISBN_OK'): # ISBN found
            toshoutil.error_exit('line %u unexpected isbn_lookup result %s' % (lno, isbn_lookup))

        # Now check the title
        isbn_title = row[4]
        spro_title = row[8]

        if isbn_title == spro_title: # exactly matched
            csvw_main.writerow(rout)
        else:
            csvw_title_unmatch.writerow(rout)



def usage():
    print('Usage: %s <OUT liblb main booklist CSV> \n\t\t<OUT libib title-unmach booklist CSV> \n\t\t<OUT libib isbn-not-found booklist CSV> \n\t\t<IN School Pro booklist CSV>' % sys.argv[0], file=sys.stderr)
#
#*****************************************************************************
# Main
#*****************************************************************************

def main():
 
    args = sys.argv

    if 5 > len(args):
        print('ERROR: missing arguments', file=sys.stderr)
        usage()
        sys.exit(1)

    # Read the input book list and add isbn use count
    fn_blist_in = args[4]

    fn_blist_main_out          = args[1]
    fn_blist_title_unmatch_out = args[2]
    fn_blist_lookup_fail_out   = args[3]

    fi_blist, cr_blist = open_csv(fn_blist_in, 'r')

    fo_blist_main, cw_blist_main = open_csv(fn_blist_main_out, 'w')
    fo_blist_title_unmatch, cw_blist_title_unmatch = open_csv(fn_blist_title_unmatch_out, 'w')
    fo_blist_lookup_fail, cw_blist_lookup_fail = open_csv(fn_blist_lookup_fail_out, 'w')

    conv_blist(cr_blist, cw_blist_main, cw_blist_title_unmatch, cw_blist_lookup_fail)

    fi_blist.close()
    fo_blist_main.close()
    fo_blist_title_unmatch.close()
    fo_blist_lookup_fail.close()


main()




