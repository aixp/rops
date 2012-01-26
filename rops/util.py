# Alexander Shiryaev, 2010

import os, sys

def readFile (fileName):
	fh = open(fileName, 'rb')
	data = fh.read()
	fh.close()
	return data

def writeFile (fileName, data, sync=True):
	fh = open(fileName, 'wb')
	fh.write(data)
	if sync:
		os.fsync(fh.fileno())
	fh.close()

def dataDir ():
	exe = sys.argv[0]
	assert exe != ''
	return os.path.dirname( os.path.realpath(exe) )
