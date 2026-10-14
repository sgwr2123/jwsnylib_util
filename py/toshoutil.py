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

def debug_print(l, msg):
    if debug_level >= l:
        print('DEBUG%u %s' % (l, msg), file=sys.stderr)

def error_exit(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)
    


class ConstMeta(type):
    def __setattr__(self, name, value):
        if name in self.__dict__:
            raise TypeError(f'Cannot rebind const ({name})')
        else:
            self.__setattr__(name, value)

#=============================================================================
# 国会図書館サーチクラス

class NDS(metaclass=ConstMeta):
    HTTP_ERROR = 2
    ISBN_NOT_FOUND =1
    ISBN_OK = 0

class ndl_search:
    def __init__(self, req_interval):
        self.req_interval = req_interval
        self.last_cpl_time = 0
        self.session = requests.Session()
        self.parms =  { 'format' : 'xml' }
        self.il_parms =  { 'format' : 'xml' }
        self.tl_parms =  { 'format' : 'xml' }
        self.num_http_trial = 4  # number of times to try HTTP
        self.wait_scale = [1, 2, 3, 5] # a little smaller than power-2

    def lookup_common(self, parms):

        endpoint = "https://iss.ndl.go.jp/api/opensearch"

        for i in range(self.num_http_trial):
            if self.last_cpl_time != 0:
                ct = time.perf_counter()
                dt = ct - self.last_cpl_time
                wt = self.wait_scale[i] * (self.req_interval - dt)
                if wt > 0: # need to wait for extra time
                    debug_print(1, 'ndl_serach: waiting for %.3f sec to meet request interval=%f sec' % (wt, self.req_interval))
                    time.sleep(wt)


            result = self.session.get(endpoint, params=parms, timeout=80)

            self.last_cpl_time = time.perf_counter()

            if (result.status_code == 429) or (result.status_code == 504):
                debug_print(1, 'ndl_serach: Got HTTP resp=%u, retring(%u)' % (result.status_code, i))
                continue # retry

            break

        if result.status_code != 200:
            return (NDS.HTTP_ERROR, result.status_code)
            # Ensure 200 for now

        book_info = xmltodict.parse(result.text)
        #pprint.pprint(book_info)
        return (NDS.ISBN_OK, book_info)

    def lookup_isbn(self, isbn):
        self.il_parms['isbn'] = isbn
        
        (rc, rv) = self.lookup_common(self.il_parms)
        if rc != NDS.ISBN_OK:
            return (rc, rv)

        x = rv['rss']['channel']
        if not 'item' in x:
            return (NDS.ISBN_NOT_FOUND, '')   # isbn not found
        if not 'dc:title' in x['item']:
            return (NDS.ISBN_NOT_FOUND, '')
        return (ISBN_OK, x['item']['dc:title'])

    def lookup_title(self, tpat):
        self.tl_parms['title'] = tpat

        (rc, rv) = self.lookup_common(self.tl_parms)
        if rc != NDS.ISBN_OK:
            #debug_print(2, 'lookup_title ERROR rc=%u' % rc)
            #pprint.pprint(rv)
            return (rc, rv)

        x = rv['rss']['channel']
        if not 'item' in x:
            debug_print(1, 'ndl.lookup_title: no item element in [rss][channel]')
            #pprint.pprint(x)
            return (NDS.ISBN_NOT_FOUND, '')   # isbn not found
        
        x = x['item']
        if isinstance(x, list): # x is a list, return
            return (NDS.ISBN_OK, x)
        elif isinstance(x, dict):
            return (NDS_ISBN_OK, [x]) # create a single-item array
        else:
            debug_print(1, 'ndl.lookup_title: neither dict nor list')
            return (NDS.ISBN_NOT_FOUND, '')


    
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
# Attempt partial/tolerant match on book titles

def filter_ttext(x):
    # pre-filter title text to eliminate disturbing characters
    r0 = re.sub(r'[ \!\:\-\.　！：ー―・．]', '', x)
    r = r0.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    debug_print(2, "filter_ttext |%s| -> |%s|" %(x, r))
    return r

class TMR(metaclass=ConstMeta):
 
    EMATCH = 0   # exact match without pre-filter
    MATCH = 1  # exact match after pre-filter
    PMATCH0 = 2  # isbn_title contained in spro_title after pre-filter
    PMATCH1 = 3  # spro_title contained in isbn_title after pre-filter
    UNMATCH = 4
    Syms = { EMATCH:'EMATCH', MATCH:'MATCH', PMATCH0:'PMATCH0', PMATCH1:'PMATCH1', UNMATCH:'UNMATCH'}
def attempt_tolerant_match(t1, t2):
    a1 = filter_ttext(t1)
    a2 = filter_ttext(t2)
  
    # (rc, a1, a2, midx)
    if t1 == t2: # match without pre-filter
        return (TMR.EMATCH, a1, a2, 0)

    if a1 == a2: # match after pre-filter
        return (TMR.MATCH, a1, a2, 0)

    r = a1.find(a2) # a2 contained in a1?
    if r >= 0:
        return (TMR.PMATCH1, a1, a2, r)

    r = a2.find(a1)
    if r >= 0:
        return (TMR.PMATCH0, a1, a2, r)

    return (TMR.UNMATCH, a1, a2, 0)
    

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



