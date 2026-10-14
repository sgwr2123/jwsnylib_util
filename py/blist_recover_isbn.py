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
from toshoutil import NDS
from toshoutil import ndl_search

toshoutil.debug_level = 1




def generate_ref_info(row, a1, a2, midx):
    x = row[0:5] 
    x += [a1, a2, midx] 
    x += row[5:]

    return x


RC_SINGLE = 1
RC_MULTI = 2
RC_NOT_FOUND = 3

#=============================================================================
def is_isbn13(x):
    #r = re.sub(r'\-', '', x)
    res = re.match(r'^9784\d{9}$', x)
    return (res != None)

def is_isbn10(x):
    #r = re.sub(r'\-', '', x)
    res = re.match(r'^\d{9}[Xx\d]$', x)
    return (res != None)

def isbn_conv10to13(x):
    x9 = x[0:9] # take first 9 characters
    y = "978%s" % x9

    # calc checksum
    s = 0
    for i in range(12):
        p = (i % 2)*2+1 # 1 or 3
        s += int(y[i]) * p
    s = s % 10
    if s != 0:
        s = 10 - s

    res = "%s%u" % (y, s)
    debug_print(2, "isbn_conv10to13 |%s| -> |%s|" % (x, res))
    return res


def cmp_isbn(ext, cur):
    if ext == '':
        return (True, cur)
    else:
        if ext == cur:
            return (True, ext)
        else:
            return (False, '')
    
# examine dc:identifier for a book item
# No ISBN info found --> return ''
# Single ISBN10/ISBN13 found --> conv to ISBN13 and return
# Multiple ISBN10/13 found and they are equivalent --> return ISBN13
# Multiple ISBN10/13 found and they don't match --> return ''

def locate_isbn(x):
    ils = x.get('dc:identifier', '')
    if isinstance(ils, dict): # conv to list
        ils = [ils]
    if not isinstance(ils, list):
        return  ''

    isbn = ''
 
    cont = True

    for i in ils:
        t = i['@xsi:type']
        v0 = i['#text']
        v = re.sub(r'\-', '', v0) # exclude '-'
        if t == 'dcndl:ISBN' or t == 'dcndl:ISBN13':
            # examine isbn
            if is_isbn13(v):
                (cont, isbn) = cmp_isbn(isbn, v)
            elif is_isbn10(v):
                v13 = isbn_conv10to13(v)
                (cont, isbn) = cmp_isbn(isbn, v13)
            else:
                cont = False # fail immediately

            if not cont:
                return ''

    # scan complete
    return isbn
    




def parse_ndl_result(x, stitle, publisher):
    if len(x) == 1:
        y = x[0]
        isbn = locate_isbn(y)
        title = y['dc:title']
        if isbn != '':
            return (RC_SINGLE, isbn, title)
    else:
        risbn = ''
        rtitle = ''
        #got_hit = 0
        for y in x:
            if 'dc:publisher' in y:
                if y['dc:publisher'] != publisher: # publisher not matched
                    continue
            #if got_hit != 0: # multiple entries
            #    return (RC_NOT_FOUND, '', '')
            #got_hit += 1

            isbn = locate_isbn(y)
            if isbn == '': # ISBN not found or not consistent
                return (RC_NOT_FOUND, '', '')

            # ISBN is good. Now ensure they match with other instances
            title = y['dc:title']
            if risbn == '': # first instance
                risbn = isbn # record isbn and title
                rtitle = title 
            else: # 2nd and later entries, compare with 1st one
                if risbn != isbn or rtitle != title:
                    return (RC_NOT_FOUND, '', '') # failed to match
        # all items have been scanned
        if risbn != '':
            return (RC_MULTI, risbn, rtitle)
        
    return (RC_NOT_FOUND, '', '')

#=============================================================================
# Read the input book list pre-processed by blist_lookup_isbn.py
# Produces 3 output booklist for Libib import (intended for different collections)
# main: The books with successful ISBN lookup and verified strict match on title
# title_unmach: Those with successful ISBN lookup but got title mismatch (likely small difference)
# lookup_fail: Those with ISBN lookup failure

def conv_blist(csvr, csvw_bl, csvw_ref, fdb):
    
    lno = 0
 
    ns = ndl_search(15)
    lim = 0

    for row in csvr:
        lno += 1

        if lno == 1: # skip the first line
            # Do emit the title lines for all 3 output book lists
            csvw_bl.writerow(row)

            ref_title = ['isbn_prechk', 'isbn_prechk_aux', 'ndl_t_lookup', 'ndl_isbn',  'ndl_title', 'atxt0', 'atxt1', 'midx' ] + row[5:]
            
            csvw_ref.writerow(ref_title)

            continue

        #rout = conv_book_info(row)

        isbn_pcheck = row[0]
        isbn_lookup = row[2]

        if isbn_pcheck != 'NO_ISBN':  # Only process No-ISBN entries
            csvw_bl.writerow(row) # no change
            continue

        stitle = row[8]
        stitle = re.sub(r'　', ' ', stitle)
        res = re.match(r'^\d+$', stitle)
        if (res != None) or (stitle == ''): # title is empty or just an integer, don't lookup
            row[2] = 'TLU_NOTITILE'
            csvw_bl.writerow(row)
            continue

        lim += 1
        if lim > 15:
            return # cut off at 5 attempts
        (rc, x) = ns.lookup_title(stitle)

        if rc == NDS.HTTP_ERROR:
            row[2] = 'TLU_HTTP_ERROR'
            row[3] = x
            csvw_bl.writerow(row)
            continue

        if rc == NDS.ISBN_NOT_FOUND:
            row[2] = 'TLU_NOT_FOUND'
            csvw_bl.writerow(row)
            continue

        if rc != NDS.ISBN_OK:
            toshoutil.error_exit('Invalid rc=%u' % rc)

        pprint.pprint(x, stream=fdb)
        # Now parse the lookup results
        (rc, isbn, ntitle) = parse_ndl_result(x, stitle, row[20])

        if rc == RC_NOT_FOUND:
            row[2] = 'TLU_NOT_FOUND'
            row[3] = len(x)
            csvw_bl.writerow(row)
            continue

        prefix = 'SGL' if rc == RC_SINGLE else 'MLT'

        (tmr, a1, a2, midx) = toshoutil.attempt_tolerant_match(stitle, ntitle)
        orc = 'TLU_%s_%s' % (prefix, TMR.Syms[tmr])
        row[2] = orc
        row[3] = isbn
        row[4] = ntitle
        csvw_bl.writerow(row)
        csvw_ref.writerow(generate_ref_info(row, a1, a2, midx))
        
            


def usage():
    print('Usage: %s <OUT intermediate booklist CSV>\n\t\t<OUT reference debug info CSV> \n\t\t<IN intermediate booklist CSV>' 
        % sys.argv[0], file=sys.stderr)
#
#*****************************************************************************
# Main
#*****************************************************************************

def main():
 
    args = sys.argv

    if 4 > len(args):
        print('ERROR: missing arguments', file=sys.stderr)
        usage()
        sys.exit(1)

    # Read the input book list and add isbn use count
    fn_blist_in = args[3]

    fn_blist_out          = args[1]
    fn_ref_out            = args[2]
    
    fi_blist, cr_blist = open_csv(fn_blist_in, 'r')

    fo_blist_out,  cw_blist_out  = open_csv(fn_blist_out, 'w')
    fo_ref_out,    cw_ref_out    = open_csv(fn_ref_out, 'w')
   
    with open('debug.log', mode='w') as fdb:

        conv_blist(cr_blist, cw_blist_out, cw_ref_out, fdb)
    
    fi_blist.close()
    fo_blist_out.close()
    fo_ref_out.close()


main()




