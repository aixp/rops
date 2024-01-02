# Windows only: associate profiles extensions with IDE
# Alexander Shiryaev, 2010

import os
import _winreg as winreg
from . import profiles

myLink = 'IDE.File'
editWithTitle = 'Edit with IDE'

def getPyVersions ():
	pyCoreKey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\Python\PythonCore')
	try:
		l = getKeys(pyCoreKey)
	finally:
		winreg.CloseKey(pyCoreKey)
	return l

def getPyDir (pyVer):
	key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\Python\PythonCore\%s\InstallPath' % (pyVer,))
	try:
		return getValues(key)['']
	finally:
		winreg.CloseKey(key)

def getPythonDir ():
	pyVersions = getPyVersions()
	pyVer = pyVersions[-1:][0]
	print('Python version:', pyVer)
	pyDir = getPyDir(pyVer)
	return pyDir

def getCmd ():
	return '"' + os.path.join(getPythonDir(), "python.exe") + '" "' + os.path.join(os.path.dirname(os.path.realpath(__file__)), 'ide-gtk2.py') + '" "%1"'

def getValues (key):
	d = {}
	i = 0
	while True:
		try:
			val = winreg.EnumValue(key, i)
		except WindowsError:
			break
		else:
			k, v, x = val
			assert x == 1
			assert k not in d
			d[k] = v
		i = i + 1
	return d

def getKeys (key):
	l = []
	i = 0
	while True:
		try:
			val = winreg.EnumKey(key, i)
		except WindowsError:
			break
		else:
			l.append(val)
		i = i + 1
	return l

def regExt (e, cmd):
	assert e.startswith('.') or (e == '*')

	print('registering:', e)

	key = winreg.CreateKey( winreg.HKEY_CLASSES_ROOT, e )
	try:
		link = getValues(key).get('')
		if link is None:
			link = myLink
			winreg.SetValueEx(key, '', 0, winreg.REG_SZ, link)
		print('	-->', link)
	finally:
		winreg.CloseKey(key)

	key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, link)
	try:
		shellKey = winreg.CreateKey(key, 'shell')
		try:
			editWithKey = winreg.CreateKey(shellKey, editWithTitle)
			try:
				commandKey = winreg.CreateKey(editWithKey, 'command')
				try:
					winreg.SetValueEx(commandKey, '', 0, winreg.REG_SZ, cmd)
				finally:
					winreg.CloseKey(commandKey)
			finally:
				winreg.CloseKey(editWithKey)
		finally:
			winreg.CloseKey(shellKey)
	finally:
		winreg.CloseKey(key)

def registerAll ():
	cmd = getCmd()
	print('command:', cmd)

	s = set()
	for prof in profiles.profiles:
		for ext in prof['extensions']:
			s.add('.' + ext)
	for e in s:
		regExt(e, cmd)

def main ():
	registerAll()

if __name__ == '__main__':
	main()
