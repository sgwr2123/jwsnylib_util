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

debug_level = 0

#=============================================================================
# 使い方: 
# blist_lookup_isbn.py  <OUT Booklist CSV> <IN School Pro booklist CSV>


def debug_print(l, msg):
    if debug_level >= l:
        print('DEBUG%u %s' % (l, msg))


#=============================================================================
# 国会図書館サーチクラス

HTTP_ERROR = 2
ISBN_NOT_FOUND =1
ISBN_OK = 0

class ndl_search:
    def __init__(self, req_interval):
        self.req_interval = req_interval
        self.last_cpl_time = 0
        self.session = requests.Session()
        self.parms =  { 'format' : 'xml' }

    def lookup_isbn(self, isbn):
        if self.last_cpl_time != 0:
            ct = time.perf_counter()
            dt = ct - self.last_cpl_time
            wt = self.req_interval - dt
            if wt > 0: # need to wait for extra time
                debug_print(2, 'ndl_serach: waiting for %.3f sec to meet request interval=%f sec' % (wt, self.req_interval))
                time.sleep(wt)

        endpoint = "https://iss.ndl.go.jp/api/opensearch"
        self.parms['isbn'] = isbn

        result = self.session.get(endpoint, params=self.parms, timeout=80)

        self.last_cpl_time = time.perf_counter()
            
        if result.status_code != 200:
            return (HTTP_ERROR, result.status_code)
            # Ensure 200 for now

        book_info = xmltodict.parse(result.text)
        x = book_info['rss']['channel']
        if not 'item' in x:
            return (ISBN_NOT_FOUND, '')   # isbn not found
        if not 'dc:title' in x['item']:
            return (ISBN_NOT_FOUND, '')
        return (ISBN_OK, x['item']['dc:title'])

#=============================================================================
# remove white space
def rmsp(s):
	
	while True:
		# 左側空白を削除
		result = re.subn(r'$[\s　]+', '', s)
		
		if result[1]:
			s = result[0]
			continue
		
		# 右側
		result = re.subn(r'[\s　]+$', '', s)
		if result[1]:
			s = result[0]
			continue
		
		break
	
	return s



#=============================================================================
# Normalize ISBN
def normalize_isbn(x):
    r = re.sub('[^\d]', '', x)
    debug_print(2, 'normalize_isbn |%s| -> |%s|' % (x, r))
    return r


#=============================================================================
# Read the input book list and populate ISBN use count
# returns (isbn_use_count_dict, book_list_row_list)
def read_blist(csvr):

    isbn_uc = {}
    lno = 0
    blrows = []

    for row in csvr:
        lno += 1
        blrows.append(row)

        if lno == 1: # skip the first line
            continue

        isbn = normalize_isbn(row[0])
        isbn_uc[isbn] = isbn_uc.get(isbn, 0) + 1 #increment isbn use count

    return (isbn_uc, blrows)

def lookup_isbn(blrows_in, isbn_uc, csvw):
    endpoint = "https://api.openbd.jp/v1/get"

    headers= {
    
    }
    params={ 
       # "isbn":"9784061538290"
    }

    session = requests.Session()

    lno = 0
    st = 0
    rt = 0
    nl = len(blrows_in)

    ns = ndl_search(10)

    for row in blrows_in:
        lno += 1

        if lno == 1:
            # write header
            csvw.writerow(('isbn_prechk', 'isbn_prechk_aux', 'isbn_lookup', 'isbn_lookup_aux', 'isbn_title', *row))
            continue

        rout = ['', '', '', '', ''] + row
        # non-title lines, attempt ISBN lookup
        isbn = normalize_isbn(row[0])

        if isbn == '': # Empty
            rout[0] = 'NO_ISBN'
            csvw.writerow(rout)
            continue

        # Non-empty ISBN
        if isbn_uc[isbn] > 1: # duplicated ISBN
            rout[0] = 'ISBN_NOT_UNIQUE'
            rout[1] = isbn_uc[isbn]
            # do lookup http
            # continue

        if rt == 0:
            rt = time.perf_counter()
        else:
            ct = time.perf_counter() 
            dt = ct - rt
            if dt >= 1.0:
                print('Processing row %u/%u' % (lno, nl), end='\r')
                rt = ct

        # ISBN non empty, now attempt web API lookup
        # ensure at least 100ms lookup interval to limit server load
        if st != 0:
            dt = time.perf_counter() - st
            if dt < 0.1: 
                time.sleep(0.1 - dt)

            
        st = time.perf_counter()
        params['isbn'] = isbn
        result = session.get(endpoint, headers=headers, params=params, timeout=10)
        if result.status_code != 200:
            # record error
            rout[2] = 'HTTP_ERROR'
            rout[3] = result.status_code
            csvw.writerow(rout)
            continue
        
        
        res = result.json()
        nel = len(res)

        # Json contents valid, write result and go to the next row
        if res[0] != None:
            t = res[0]["onix"]["DescriptiveDetail"]["TitleDetail"]["TitleElement"]["TitleText"]["content"]
            rout[2] = 'ISBN_OK'
            rout[3] = nel
            rout[4] = t
            csvw.writerow(rout)
            continue

        # OpenBD lookup failed! Now try NDL.
        (rc, t) = ns.lookup_isbn(isbn)

        if rc == HTTP_ERROR:
            rout[2] = 'NDL_HTTP_ERROR'
            rout[3] = t
        elif rc == ISBN_NOT_FOUND:
            rout[2] = 'NDL_ISBN_NOT_FOUND'

        elif rc == ISBN_OK:
            rout[2] = 'NDL_ISBN_OK'
            rout[4] = t
        else:
            rout[2] = 'PROG_ERROR'
        csvw.writerow(rout)


        # JSON looks good, now populate title info
        
    print('\nlookup_isbn(): DONE')
    return 

def usage():
    print('Usage: %s <OUT Booklist CSV> <IN School Pro booklist CSV>' % sys.argv[0], file=sys.stderr)
#=============================================================================
# CSVファイルを開く

def open_csv(fname, mode): # mode は 'w' か 'r'

	ms = '書き込み' if mode == 'w' else '読み込み'

	try:
		f  = codecs.open(fname, mode, 'utf_8')
		cw = csv.writer(f) if mode == 'w' else csv.reader(f)
		return (f, cw)
	except:
		print('エラー:ファイル', fname, 'を', ms, 'モードで開けません', 
			  file=sys.stderr)
		sys.exit(1)

#*****************************************************************************
# Main
#*****************************************************************************

def main():
 
    args = sys.argv

    if 3 > len(args):
        print('ERROR: missing arguments', file=sys.stderr)
        usage()
        sys.exit(1)

    # Read the input book list and add isbn use count
    fn_blist_in = args[2]

    fi_blist, cr_blist = open_csv(fn_blist_in, 'r')

    (isbn_use_count, blrows) = read_blist(cr_blist)

    fi_blist.close()

    # Second time scan with ISBN lookup, and emit the output CSV
    fn_blist_out = args[1]

    fo_blist, cw_blist = open_csv(fn_blist_out, 'w')

    lookup_isbn(blrows, isbn_use_count, cw_blist)

    fo_blist.close()


main()




