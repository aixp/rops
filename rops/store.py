# Alexander Shiryaev, 2010

import os, sys
import cPickle as pickle

if sys.platform == 'win32':
	storeDir = os.path.join(os.getenv('APPDATA'), '.ide')
else:
	storeDir = os.path.join(os.getenv('HOME'), '.ide')

def load (name, default):
	fileName = os.path.join(storeDir, name)
	try:
		fh = open(fileName, 'rb')
	except Exception, e:
		print 'Exception on open %s db:' % (name,), repr(e), e
		data = default
	else:
		try:
			try:
				data = pickle.load(fh)
			except Exception, e:
				print 'Exception on load %s db:' % (name,), repr(e), e
				data = default
		finally:
			fh.close()
	return data

# return values: False | True
def save (name, data):
	if not os.path.exists(storeDir):
		try:
			os.mkdir(storeDir)
		except Exception, e:
			print 'Error on mkdir %s:' % (repr(storeDir),), repr(e), e
			return False

	fileName = os.path.join(storeDir, name)
	try:
		fh = open(fileName, 'wb')
	except Exception, e:
		print 'Exception on open %s db:' % (name,), repr(e), e
		return False
	else:
		try:
			try:
				pickle.dump(data, fh, protocol=2)
			except Exception, e:
				print 'Exception on save %s db:' % (name,), repr(e), e
				return False
			else:
				return True
		finally:
			fh.close()
