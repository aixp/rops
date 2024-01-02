# Alexander Shiryaev, 2010, 2024

import os

def readFile (fileName):
	with open(fileName, 'rb') as fh:
		return fh.read()

def writeFile (fileName: str, data: bytes, sync: bool = True):
	assert type(data) is bytes

	with open(fileName, 'wb') as fh:
		fh.write(data)
		if sync:
			os.fsync(fh.fileno())

def dataDir ():
	return os.path.dirname(__file__)
