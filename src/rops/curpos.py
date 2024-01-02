# -*- coding: utf-8 -*-
# Alexander Shiryaev, 2010, 2024

import os

from . import store

Trace = True

storeName = 'curpos'

CUR_POS_DB_LEN = 1000

def loadCurPos (fileName: str):
	assert fileName is not None

	db = store.load(storeName, None)
	if db is not None:
		r = db.get( os.path.realpath(fileName) )
		if r is not None:
			line, col, last = r
			if Trace: print('loaded cursor position:', line, col)
			return line, col
		else:
			if Trace: print('can not restore cursor position: not saved')
			return 0, 0
	else:
		return 0, 0

def saveCurPos (fileName: str, line: int, col: int):
	assert fileName is not None

	if (line == 0) and (col == 0):
		pass
	else:
		db = store.load(storeName, {})

		key = os.path.realpath(fileName)
		oldVal = db.get(key)
		if oldVal is None:
			toDel = None
			for k, v in db.iteritems():
				l, c, last = v
				if last == CUR_POS_DB_LEN - 1:
					assert toDel is None
					toDel = k
				else:
					db[k] = (l, c, last + 1)
			if toDel is not None:
				del db[toDel]
				if Trace: print(toDel, 'removed from cursor position db')
		else:
			oldLast = oldVal[2]
			for k, v in db.iteritems():
				l, c, last = v
				if last < oldLast:
					db[k] = (l, c, last + 1)

		db[key] = (line, col, 0)

		ok = store.save(storeName, db)
		if ok:
			if Trace: print('saved cursor position:', line, col)
