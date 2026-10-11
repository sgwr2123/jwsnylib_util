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
import copy

import toshoutil

from toshoutil import debug_print
from toshoutil import open_csv
from toshoutil import TMR

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


def generate_ref_info(row, rc, a1, a2, midx):
    x = row[0:3] 
    x += row[4:5] 
    x += [TMR.Syms[rc], a1, a2, midx] 
    x += row[5:]

    return x



#=============================================================================
# Read the input book list pre-processed by blist_lookup_isbn.py
# Produces 3 output booklist for Libib import (intended for different collections)
# main: The books with successful ISBN lookup and verified strict match on title
# title_unmach: Those with successful ISBN lookup but got title mismatch (likely small difference)
# lookup_fail: Those with ISBN lookup failure

def conv_blist(csvr, csvw_main, csvw_main_ref, csvw_tofix):
    
    lno = 0
    main_title = ['ean_isbn13', 'added', 'call_number', 'ddc', 'lcc' ]
    for row in csvr:
        lno += 1

        if lno == 1: # skip the first line
            # Do emit the title lines for all 3 output book lists
            csvw_main.writerow(main_title)
            ref_title = ['isbn_prechk', 'isbn_prechk_aux', 'isbn_lookup', 'isbn_title',  'match_rc', 'atxt0', 'atxt1', 'midx' ] + row[5:]
            tofix_title = row
            
            csvw_main_ref.writerow(ref_title)
            csvw_tofix.writerow(tofix_title)
            continue

        rout = conv_book_info(row)

        isbn_pcheck = row[0]
        isbn_lookup = row[2]

        if isbn_pcheck == 'NO_ISBN':  # Books w/o/ ISBN. Skip
            continue

        #if isbn_pcheck == 'ISBN_NOT_UNIQUE': # books with non-unique ISBN, skip
        #    continue
        # Do accept books with duplicate ISBN. Later execute human tasks to eliminate duplicated books

        if isbn_lookup == 'NDL_HTTP_ERROR': # Those that got HTTP error for NDL search. Skip for now.
            continue
    
        # Pre-check passed. This book can be added in one of the 3 output list.

        if isbn_lookup == 'NDL_ISBN_NOT_FOUND': # ISBN not found both in OpenBD and NDL
            # human to-fix list
            csvw_tofix.writerow(row)
            continue


        if (isbn_lookup != 'ISBN_OK') and (isbn_lookup != 'NDL_ISBN_OK'): # ISBN found
            toshoutil.error_exit('line %u unexpected isbn_lookup result %s' % (lno, isbn_lookup))

        # Now check the title
        isbn_title = row[4]
        spro_title = row[8]
        (rc, a1, a2, midx) = toshoutil.attempt_tolerant_match(isbn_title, spro_title)
        if rc < TMR.UNMATCH:
            # success, write the main book list
            csvw_main.writerow(rout)
            csvw_main_ref.writerow(generate_ref_info(row, rc, a1, a2, midx))
        else:
            # match failed, needs human review
            csvw_tofix.writerow(row)
            


def usage():
    print('Usage: %s <OUT liblb-ready main booklist CSV> \n\t\t<OUT reference info CSV for main booklist> \n\t\t<OUT booklist to be fixed by human CSV> \n\t\t<IN School Pro booklist CSV>' % sys.argv[0], file=sys.stderr)
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
    fn_ref_main_out            = args[2]
    fn_blist_tofix_out         = args[3]

    fi_blist, cr_blist = open_csv(fn_blist_in, 'r')

    fo_blist_main,  cw_blist_main  = open_csv(fn_blist_main_out, 'w')
    fo_ref_main,    cw_ref_main    = open_csv(fn_ref_main_out, 'w')
    fo_blist_tofix, cw_blist_tofix = open_csv(fn_blist_tofix_out, 'w')

    conv_blist(cr_blist, cw_blist_main, cw_ref_main, cw_blist_tofix)

    fi_blist.close()
    fo_blist_main.close()
    fo_ref_main.close()
    fo_blist_tofix.close()


main()




