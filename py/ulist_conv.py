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
from toshoutil import error_exit
from toshoutil import open_csv

toshoutil.debug_level = 2


def usage():
    print('Usage: %s <OUT Userlist CSV> <IN School Pro userlist CSV>' % sys.argv[0], file=sys.stderr)



#=============================================================================
# Read the input book list and populate ISBN use count
# returns (isbn_use_count_dict, book_list_row_list)
def conv_ulist(csvr, csvw):

    ulist_dic = {}
    lno = 0
    plist = []

    for row in csvr:
        lno += 1

        if lno == 1: # skip the first line
            csvw.writerow(['Patron ID', '']) # only 1 column
            continue

        # 2nd and later, the actual data
        suid = row[0]
        result = re.match(r'^(\d+)$', suid)
        if result == None:
            error_exit('ERROR: line %u Invalid user ID |%s|' % (lno, suid))

        uid = int(suid)
        if uid == 0:
            error_exit('ERROR user ID == 0 (%s)' % suid)

        uid = uid % 1000000 # take 6 lower digits

        if uid in ulist_dic:
            error_exit('ERROR line %u user ID %u/%s defined twice' % (lno, uid, suid))
        ulist_dic[uid] = 1

        csvw.writerow([uid, ''])
        plist.append(uid+99000000)
    for x in plist:
        csvw.writerow([x, ''])


#*****************************************************************************
# Main
#*****************************************************************************

def main():
 
    args = sys.argv

    if 3 > len(args):
        print('ERROR: missing arguments', file=sys.stderr)
        usage()
        sys.exit(1)

    fn_ulist_out = args[1]
    fn_ulist_in  = args[2]

    fi_ulist, cr_ulist = open_csv(fn_ulist_in, 'r')
    fo_ulist, cw_ulist = open_csv(fn_ulist_out, 'w')

    conv_ulist(cr_ulist, cw_ulist)
    
    fi_ulist.close()
    fo_ulist.close()


main()




