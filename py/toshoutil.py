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
        print('DEBUG%u %s' % (l, msg))

def error_exit(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)
    
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



