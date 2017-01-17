# -*- coding: utf-8 -*-
# Alexander Shiryaev, 2010

import os, re
from util import dataDir

Trace = True

d = None

def tr (s):
	global d
	assert type(s) is str # not unicode
	assert s.startswith('#')

	f = s[1:]

	if d != None:
		t = d.get(f, None)
		if t != None:
			return t
		else:
			print 'NO TRANSLATION:', f
			return unicode(f)
	else:
		return unicode(f)

def load (lang):
	# fileName = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'translations', lang)
	fileName = os.path.join( dataDir(), 'translations', lang )
	if Trace: print 'translation file:', fileName
	if os.path.exists(fileName):
		fh = open(fileName, 'rb')
		d = {}
		encoding = fh.readline().rstrip()
		while True:
			line = fh.readline()
			if line == '':
				break
			if line != '\n':
				l = line.rstrip().split('\t')
				while True:
					try:
						l.remove('')
					except ValueError:
						break
				f, t = l
				d[f] = t.decode(encoding)
		fh.close()
		return d
	else:
		if Trace: print 'no translation file found'
		return None

def setLang (lc):
	global d
	if Trace: print 'set translation lang:', lc
	d = load(lc)
