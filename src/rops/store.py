# Alexander Shiryaev, 2010, 2024

import os, sys, pickle
import pickle
import appdirs

storeDir = os.path.join(appdirs.user_config_dir(), 'rops')

def load (name: str, default):
	fileName = os.path.join(storeDir, name)
	try:
		fh = open(fileName, 'rb')
	except Exception as e:
		print('Exception on open %s db:' % (name,), repr(e), e)
		data = default
	else:
		try:
			try:
				data = pickle.load(fh)
			except Exception as e:
				print('Exception on load %s db:' % (name,), repr(e), e)
				data = default
		finally:
			fh.close()
	return data

def save (name: str, data) -> bool:
	if not os.path.exists(storeDir):
		try:
			os.mkdir(storeDir)
		except Exception as e:
			print('Error on mkdir %s:' % (repr(storeDir),), repr(e), e)
			return False

	fileName = os.path.join(storeDir, name)
	try:
		fh = open(fileName, 'wb')
	except Exception as e:
		print('Exception on open %s db:' % (name,), repr(e), e)
		return False
	else:
		try:
			try:
				pickle.dump(data, fh, protocol=2)
			except Exception as e:
				print('Exception on save %s db:' % (name,), repr(e), e)
				return False
			else:
				return True
		finally:
			fh.close()
