# -*- coding: utf-8 -*-
#
# Alexander Shiryaev, 2010-2017, 2021, 2024
#

import re, subprocess, os, sys, locale, tempfile, time, errno, traceback
from . import util, winenc
from .translate import tr
from . import cocodrivers

mswindows = (sys.platform == 'win32')

if not mswindows:
	import fcntl # for cmdPollOnly

Trace = True

def sameFile (fn1, fn2):
	if mswindows:
		return os.path.realpath(fn1) == os.path.realpath(fn2)
	else:
		return os.path.samefile(fn1, fn2)

def cmd (args, input=None):
	if Trace: print('cmd', args)

	if input is None:
		inp = None
	else:
		inp = subprocess.PIPE

	close_fds = not mswindows
	p = subprocess.Popen(args, bufsize=8192, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=inp, close_fds=close_fds)

	if input is not None:
		p.stdin.write(input)

	o, e = p.communicate()

	return e, o

# not mswindows
def setnonblock (fd):
	flags = fcntl.fcntl(fd, fcntl.F_GETFL)
	flags = flags | os.O_NONBLOCK
	fcntl.fcntl(fd, fcntl.F_SETFL, flags)

# не ждём завершения дочерних процессов (wine)
# not mswindows
def cmdPollOnly (args):
	if Trace: print('cmdPollOnly', args)

	close_fds = not mswindows
	p = subprocess.Popen(args, bufsize=8192, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=close_fds)

	setnonblock(p.stderr)
	setnonblock(p.stdout)

	t0 = time.time()
	pollDone = False
	e = b''
	eDone = False
	o = b''
	oDone = False
	while (not (pollDone and eDone and oDone)) and (time.time() - t0 < 10.0):
		if not pollDone:
			x = p.poll()
			pollDone = x is not None
			if pollDone:
				if Trace: print('poll done')
		if not eDone:
			try:
				x = p.stderr.read()
			except IOError as ex:
				if ex.strerror == 'Resource temporarily unavailable':
					pass
				elif ex.errno == errno.EAGAIN: # 'Resource temporarily unavailable'
					pass
				else:
					print('e IOerror', repr(ex))
			else:
				if x is None:
					pass
				elif x == b'':
					eDone = True
					if Trace: print('stderr done')
				else:
					e = e + x
		if not oDone:
			try:
				x = p.stdout.read()
			except IOError as ex:
				if ex.strerror == 'Resource temporarily unavailable':
					pass
				elif ex.errno == errno.EAGAIN: # 'Resource temporarily unavailable'
					pass
				else:
					print('o IOError', repr(ex))
			else:
				if x is None:
					pass
				elif x == b'':
					oDone = True
					if Trace: print('stdout done')
				else:
					o = o + x
	if not (pollDone and eDone and oDone):
		print('Timeout')

	p.stderr.close()
	p.stdout.close()

	return e, o

# exMsg = lambda e: str(e)
exMsg = lambda e: ''.join(traceback.format_exception(e))

_pMod = re.compile('^\s*MODULE\s+([a-zA-Z][a-zA-Z0-9]*)\s*;')
_poo2cMod = re.compile('^\s*MODULE\s+([a-zA-Z][a-zA-Z0-9]*)\s*(?:\[[^\]]+\]\s*)?;')

_pcLineCol = re.compile('^(?:[^:]+):([1-9][0-9]*):([1-9][0-9]*): ([^\n]+)\n')
_pcLine = re.compile('^(?:[^:]+):([1-9][0-9]*): ([^\n]+)\n')

_pPas = re.compile('^\s*(?:program|unit|library)\s+([a-zA-Z][a-zA-Z0-9]*)\s*;', re.I)

# "    pos    20  err 41  END missing"
# "  pos 14167  warning 307  no ELSE symbol after CASE statement sequence may lead to trap  24124 chars."
_pVocPos = re.compile("^\s*pos\s+([0-9]+)\s+(err|warning)\s+([0-9]+)\s+([^\n]+)\n")

def posToLineCol0 (src, pos):
	line = 0
	for l in map(len, src.split('\n')): # XXX: split
		if pos > l + 1:
			pos = pos - l - 1
			line = line + 1
		else:
			return (line, pos)

def vocCompile (flag, text: str, encodedText: bytes, encoding: str, fileName: str | None):
	assert type(text) is str
	assert type(encodedText) is bytes
	assert encoding is not None

	xCmd = 'voc'

	fd, name = tempfile.mkstemp()
	try:
		try:
			try:
				os.write(fd, encodedText)
			except Exception as e:
				msg = tr('#File write error') + ': ' + exMsg(e)
				return (msg, None, None)
		finally:
			try:
				os.close(fd)
			except:
				pass
		try:
			if mswindows:
				e, o = cmd([xCmd, "-f", flag, name])
			else:
				e, o = cmd(["env", "LANG=C", xCmd, "-f", flag, name])
		except Exception as e:
			msg = xCmd + ': ' + exMsg(e)
			return (msg, None, None)
	finally:
		try:
			os.remove(name)
		except:
			pass

	e = e.decode(encoding)
	o = o.decode(encoding)
	msg = e + o

	eLines = e.count('\n')
	errs = []
	warns = []
	i = eLines
	for l in o.split('\n'):
		r = _pVocPos.match(l + '\n')
		if r is not None:
			line, col = posToLineCol0(text, int(r.group(1)) + 1)
			error = r.group(4)
			pos = (line, col)
			link = (i, pos)
			if r.group(2) == 'err':
				errs.append(link)
			elif r.group(2) == 'warning':
				warns.append(link)
			else:
				assert False
		i = i + 1
	return (msg, errs, warns)

vocO2Compile = lambda text, encodedText, encoding, fileName: vocCompile('-O2', text, encodedText, encoding, fileName)
vocOCCompile = lambda text, encodedText, encoding, fileName: vocCompile('-OC', text, encodedText, encoding, fileName)

def oo2cCompile (text: str, encodedText: bytes, encoding: str, fileName: str | None):
	assert type(text) is str
	assert type(encodedText) is bytes
	assert encoding is not None

	# suffix = '.Mod'
	xCmd = 'oo2c'

	for l in text.split('\n')[:2]:
		r = _poo2cMod.match(l)
		if r is not None:
			break
	else:
		r = None

	if r is not None:
		modName = r.group(1)

		fd, name = tempfile.mkstemp(prefix=modName + '.')
		try:
			try:
				try:
					os.write(fd, encodedText.replace(b'\t', b' '))
				except Exception as e:
					msg = tr('#File write error') + ': ' + exMsg(e)
					return (msg, None, None)
			finally:
				try:
					os.close(fd)
				except:
					pass
			try:
				e, o = cmd([xCmd, name])
			except Exception as e:
				msg = xCmd + ': ' + exMsg(e)
				return (msg, None, None)
		finally:
			try:
				os.remove(name)
			except:
				pass

		e = e.decode(encoding)
		o = o.decode(encoding)
		msg = e + o

		eLines = e.count('\n')
		errs = []
		warns = []
		i = eLines
		for l in o.split('\n'):
			r = _pcLineCol.match(l + '\n')
			if r is not None:
				line = int(r.group(1)) - 1
				col = int(r.group(2)) - 1
				pos = (line, col)
				m = r.group(3)
				link = (i, pos)
				if m.startswith('Warning: '):
					warns.append(link)
				else:
					errs.append(link)
			i = i + 1
		return (msg, errs, warns)

	else:
		msg = "'MODULE Ident;' expected"
		return (msg, None, None)


_dev0Pos = re.compile("^  pos =  ([0-9]+), error = '([^']+)'$")

def dev0Compile (text: str, encodedText: bytes, encoding: str, fileName: str | None):
	assert type(text) is str
	assert type(encodedText) is bytes
	assert encoding is not None

	xCmd = 'blackbox'

	fd, name = tempfile.mkstemp()
	try:
		try:
			try:
				os.write(fd, encodedText)
			except Exception as e:
				msg = tr('#File write error') + ': ' + exMsg(e)
				return (msg, None, None)
		finally:
			try:
				os.close(fd)
			except:
				pass
		try:
			e, o = cmd([xCmd], "ConsCompiler.Compile('%s', '%s')\n" % (os.path.dirname(name), os.path.basename(name),))
		except Exception as e:
			msg = xCmd + ': ' + exMsg(e)
			return (msg, None, None)
	finally:
		try:
			os.remove(name)
		except:
			pass

	e = e.decode(encoding)
	o = o.decode(encoding)
	msg = e + o

	eLines = e.count('\n')
	errs = []
	warns = []
	i = eLines
	for l in o.split('\n'):
		r = _dev0Pos.match(l)
		if r is not None:
			line, col = posToLineCol0(text, int(r.group(1)))
			error = r.group(2)
			pos = (line, col)
			link = (i, pos)
			errs.append(link)
		i = i + 1
	return (msg, errs, warns)

# not mswindows
def winePath (fileName: str):
	args = ["winepath", "-w", fileName]
	try:
		e, o = cmdPollOnly(args)
	except Exception as e:
		return False, 'winepath: ' + ' '.join(args) + ': ' + exMsg(e)
	else:
		if e == b'':
			return True, o.rstrip()
		else:
			return False, '%s: %s' % (tr('#Error'), e.decode(locale.getpreferredencoding()))

# unified lines separator, strip empty lines, remove duplicate lines
def dcc32FilterStdout (o: bytes):
	r = []
	lastL = b''
	for l in o.split(b'\r'):
		for l1 in l.split(b'\n'):
			if (l1 != b'') and (lastL != l1):
				r.append(l1)
				lastL = l1
	return b'\n'.join(r)

_pdcc32Line = re.compile('^([^\(]+)\(([0-9]+)\) ([^\n]+)\n')

def dcc32Compile (text: str, encodedText: bytes, encoding: str, fileName: str | None):
	assert type(text) is str
	assert type(encodedText) is bytes
	assert encoding is not None

	r = _pPas.match(text)
	if r is not None:
		modName = r.group(1)
		baseName = modName + '.$$$'

		if fileName is None:
			fName = baseName
			inCurDir = True
		else:
			d = os.path.dirname(fileName)
			if (d == '') or sameFile(os.getcwd(), d):
				fName = baseName
				inCurDir = True
			else:
				fName = os.path.join(d, baseName)
				inCurDir = False

		if not os.path.exists(fName):
			try:
				try:
					util.writeFile( fName, encodedText.replace(b'\t', b' '), sync=False )
				except Exception as e:
					msg = tr('#File write error') + ': ' + exMsg(e)
					return (msg, None, None)
				if mswindows:
					try:
						e, o = cmd(["dcc32", "-R+", fName])
					except Exception as e:
						msg = 'dcc32: ' + exMsg(e)
						return (msg, None, None)
				else:
					if not inCurDir:
						ok, s = winePath(fName)
						if not ok:
							return (s, None, None)
					else:
						s = baseName
					try:
						e, o = cmdPollOnly(["wine", "dcc32", "-R+", s])
					except Exception as e:
						msg = 'wine dcc32: ' + exMsg(e)
						return (msg, None, None)
				o = dcc32FilterStdout(o)

				# указываем кодировку вывода такую же, как и кодировка содержимого файла, хотя скорее всего dcc32 использует только ascii-кодировку
				e = e.decode(encoding)
				o = o.decode(encoding)
				msg = e + o

				eLines = e.count('\n')
				errs = []
				warns = []
				i = eLines
				for l in o.split('\n'):
					r = _pdcc32Line.match(l + '\n')
					if (r is not None) and (r.group(1) == baseName):
						line = int(r.group(2)) - 1
						pos = (line, None)
						link = (i, pos)
						m = r.group(3)
						if m.startswith('Error:') or m.startswith('Fatal:'):
							errs.append(link)
						else:
							warns.append(link)
					i = i + 1
				return (msg, errs, warns)
			finally:
				try:
					os.remove(fName)
				except:
					pass
		else:
			msg = "%s: %s %s %s!" % (tr('#Error'), tr('#file'), fName, tr('#already exists'))
			return (msg, None, None)
	else:
		msg = "'program ident;' or 'unit ident;' or 'library ident;' expected"
		return (msg, None, None)

_pfpcLine = re.compile('^([^\(]+)\(([0-9]+),([0-9]+)\) ([^\n]+)\n')

def fpcCompile (text: str, encodedText: bytes, encoding: str, fileName: str | None):
	assert type(text) is str
	assert type(encodedText) is bytes
	assert encoding is not None

	r = _pPas.match(text)
	if r is not None:
		modName = r.group(1)
		baseName = modName + '.$$$'

		if fileName == None:
			fName = baseName
			# inCurDir = True
		else:
			d = os.path.dirname(fileName)
			if (d == '') or sameFile(os.getcwd(), d):
				fName = baseName
				# inCurDir = True
			else:
				fName = os.path.join(d, baseName)
				# inCurDir = False

		if not os.path.exists(fName):
			try:
				try:
					util.writeFile( fName, encodedText.replace(b'\t', b' '), sync=False )
				except Exception as e:
					msg = tr('#File write error') + ': ' + exMsg(e)
					return (msg, None, None)

				try:
					e, o = cmd(["fpc", fName])
				except Exception as e:
					msg = 'fpc: ' + exMsg(e)
					return (msg, None, None)

				e = e.decode(encoding)
				o = o.decode(encoding)
				msg = e + o

				eLines = e.count('\n')
				errs = []
				warns = []
				i = eLines
				for l in o.split('\n'):
					r = _pfpcLine.match(l + '\n')
					if (r is not None) and (r.group(1) == baseName):
						line = int(r.group(2)) - 1
						col = int(r.group(3)) - 1
						pos = (line, col)
						link = (i, pos)
						m = r.group(4)
						if m.startswith('Error:') or m.startswith('Fatal:'):
							errs.append(link)
						else:
							warns.append(link)
					i = i + 1
				return (msg, errs, warns)
			finally:
				try:
					os.remove(fName)
				except:
					pass
		else:
			msg = "%s: %s %s %s!" % (tr('#Error'), tr('#file'), fName, tr('#already exists'))
			return (msg, None, None)
	else:
		msg = "'program ident;' or 'unit ident;' or 'library ident;' expected"
		return (msg, None, None)

_pgpcpLine = re.compile("^ *([0-9]+) +")

def gpcpCompile (text:str, encodedText: bytes, encoding: str, fileName: str | None):
	assert type(text) is str
	assert type(encodedText) is bytes
	assert encoding is not None

	r = _pMod.match(text)
	if r is not None:
		modName = r.group(1)
		baseName = modName + '.$$$'

		if not os.path.exists(baseName):
			try:
				try:
					util.writeFile( baseName, encodedText.replace(b'\t', b' '), sync=False )
				except Exception as e:
					msg = tr('#File write error') + ': ' + exMsg(e)
					return (msg, None, None)

				try:
					e, o = cmd(["gpcp", "/nodebug", "/hsize=32000", "/unsafe", baseName])
				except Exception as e:
					msg = 'gpcp: ' + exMsg(e)
					return (msg, None, None)

				e = e.decode(encoding)
				o = o.decode(encoding)
				msg = e + o

				eLines = e.count('\n')
				errs = []
				warns = []
				i = eLines
				state = 0 # 0 - outside, 1 - line pos matched
				for l in o.split('\n'):
					if state == 0:
						r = _pgpcpLine.match(l)
						if r is not None:
							line = int(r.group(1)) - 1
							state = 1 # line pos matched
					elif state == 1:
						if ' Warning: ' in l:
							x = warns
						else:
							x = errs
						col = l.split('^')[0].count('-')
						pos = (line, col)
						x.append( (i - 1, pos) )
						x.append( (i, pos) )
						state = 0 # outside
					i = i + 1
				return (msg, errs, warns)

			finally:
				try:
					os.remove(baseName)
				except:
					pass
		else:
			msg = "%s: %s %s %s!" % (tr('#Error'), tr('#file'), baseName, tr('#already exists'))
			return (msg, None, None)

	else:
		msg = "'MODULE Ident;' expected"
		return (msg, None, None)

_paLineCol = re.compile('^ *([0-9]+) +([0-9]+) *(Error|Warning): *([^\n]+)\n')

def astrobeCompile (text: str, encodedText: bytes, encoding: str, fileName: str | None, astrobe: int):
	assert type(text) is str
	assert type(encodedText) is bytes
	assert encoding is not None

	if astrobe == 0: # LPC2000
		astrobeDir = "Astrobe Professional Edition"
	elif astrobe == 1: # Cortex-M3
		astrobeDir = "AstrobeM3 Professional Edition"
	elif astrobe == 2: # Cortex-M4
		astrobeDir = "AstrobeM4 Professional Edition"
	else:
		assert False

	r = _pMod.match(text)
	if r is not None:
		modName = r.group(1)
		baseName = modName + '.$$$'

		if fileName is None:
			fName = baseName
			inCurDir = True
		else:
			d = os.path.dirname(fileName)
			if (d == '') or sameFile(os.getcwd(), d):
				fName = baseName
				inCurDir = True
			else:
				fName = os.path.join(d, baseName)
				inCurDir = False

		if not os.path.exists(fName):
			try: # for remove file fName
				try:
					util.writeFile( fName, encodedText.replace(b'\t', b' '), sync=False )
				except Exception as e:
					msg = tr('#File write error') + ': ' + exMsg(e)
					return (msg, None, None)
				isMono = False
				if mswindows:
					exe = os.path.join( os.getenv('ProgramFiles'), astrobeDir, 'AstrobeCompile.exe' )
					try:
						if astrobe in (1, 2): # M3 or M4
							e, o = cmd([exe, 'config.ini', fName])
						elif astrobe == 0: # LPC2000
							e, o = cmd([exe, fName])
						else:
							assert False
					except Exception as e:
						msg = 'AstrobeCompile: ' + exMsg(e)
						return (msg, None, None)
				else: # not mswindows
					tryWine = False
					if tryWine:
						if not inCurDir:
							ok, s = winePath(fName)
							if not ok:
								return (s, None, None)
						else:
							s = baseName
						try:
							if astrobe in (1, 2): # M3 or M4
								e, o = cmdPollOnly(["wine", "C:\\Program Files\\%s\\AstrobeCompile.exe" % (astrobeDir,), 'config.ini', s])
							elif astrobe == 0: # LPC2000
								e, o = cmdPollOnly(["wine", "C:\\Program Files\\%s\\AstrobeCompile.exe" % (astrobeDir,), s])
							else:
								assert False
							tryMono = False
						except Exception as e:
							if e.errno == errno.ENOENT:
								tryMono = True
							else:
								msg = 'wine AstrobeCompile: ' + exMsg(e)
								return (msg, None, None)
					else:
						tryMono = True
					if tryMono:
						try:
							if astrobe in (1, 2): # M3 or M4
								e, o = cmdPollOnly(["env", "MONO_IOMAP=all", "mono", os.path.join(os.getenv('HOME'), "install", astrobeDir, "AstrobeCompile.exe"), 'config.ini', fName])
							elif astrobe == 0: # LPC2000
								e, o = cmdPollOnly(["env", "MONO_IOMAP=all", "mono", os.path.join(os.getenv('HOME'), "install", astrobeDir, "AstrobeCompile.exe"), fName])
							else:
								assert False
							isMono = True
						except Exception as e:
							msg = 'mono AstrobeCompile: ' + exMsg(e)
							return (msg, None, None)
				e = e.decode(encoding)
				o = o.decode(encoding)
				msg = e + o

				eLines = e.count('\n')
				errs = []
				warns = []
				i = eLines
				if isMono:
					sep = '\n'
				else:
					sep = '\r\n'
				for l in o.split(sep):
					r = _paLineCol.match(l + '\n')
					if r is not None:
						line = int(r.group(1)) - 1
						col = int(r.group(2)) - 1
						pos = (line, col)
						link = (i, pos)
						m = r.group(4)
						if r.group(3) == 'Warning':
							warns.append(link)
						else:
							errs.append(link)
					i = i + 1
				return (msg, errs, warns)
			finally:
				try:
					os.remove(fName)
				except:
					pass
		else:
			msg = "%s: %s %s %s!" % (tr('#Error'), tr('#file'), fName, tr('#already exists'))
			return (msg, None, None)
	else:
		msg = "'MODULE Ident;' expected"
		return (msg, None, None)

astrobeCompileLPC2000 = lambda text, encodedText, encoding, fileName: astrobeCompile(text, encodedText, encoding, fileName, 0)
astrobeCompileM3 = lambda text, encodedText, encoding, fileName: astrobeCompile(text, encodedText, encoding, fileName, 1)
astrobeCompileM4 = lambda text, encodedText, encoding, fileName: astrobeCompile(text, encodedText, encoding, fileName, 2)

def cCompile (text: str, encodedText: bytes, encoding: str, fileName: str):
	assert type(text) is str
	assert type(encodedText) is bytes
	assert encoding is not None
	assert fileName is not None # because compileSavedOnly

	name = '.'.join(os.path.basename(fileName).split('.')[:-1])
	try:
		e, o = cmd(["make", name + '.o'])
	except Exception as e:
		msg = 'make: ' + exMsg(e)
		return (msg, None, None)

	e = e.decode(encoding)
	o = o.decode(encoding)
	msg = e + o

	def add (m, link):
		if m.startswith('warning:'):
			warns.append(link)
		else:
			errs.append(link)

	i = 0
	errs = []
	warns = []
	for l in e.split('\n'):
		r = _pcLineCol.match(l + '\n')
		if r is not None:
			line = int(r.group(1)) - 1
			col = int(r.group(2)) - 1
			pos = (line, col)
			link = (i, pos)
			m = r.group(3)
			add(m, link)
		else:
			r = _pcLine.match(l + '\n')
			if r is not None:
				line = int(r.group(1)) - 1
				pos = (line, None)
				link = (i, pos)
				m = r.group(2)
				add(m, link)
		i = i + 1
	return (msg, errs, warns)

_pGenieLineCol = re.compile('^([^:]+):([1-9][0-9]*)\.([1-9][0-9]*)-([1-9][0-9]*)\.([1-9][0-9]*): ([^\n]+)\n')

def genieCompile (text: str, encodedText: bytes, encoding: str, fileName: str):
	assert type(text) is str
	assert type(encodedText) is bytes
	assert encoding is not None
	assert fileName is not None # because compileSavedOnly

	try:
		e, o = cmd(["make"])
	except Exception as e:
		msg = 'make: ' + exMsg(e)
		return (msg, None, None)

	e = e.decode(encoding)
	o = o.decode(encoding)
	msg = e + o

	def add (m, link):
		if m.startswith('warning:'):
			warns.append(link)
		else:
			errs.append(link)

	i = 0
	errs = []
	warns = []
	for l in e.split('\n'):
		r = _pGenieLineCol.match(l + '\n')
		if r is not None:
			if sameFile(r.group(1), fileName):
				line = int(r.group(2)) - 1
				col = int(r.group(3)) - 1
				pos = (line, col)
				link = (i, pos)
				m = r.group(6)
				add(m, link)
		i = i + 1

	return (msg, errs, warns)

_zcLineCol = re.compile("^([0-9]+): ([^\(]+)\(([0-9]+)\,([0-9]+)\): ([^\n]+)\n")

def zcCompile (text: str, encodedText: bytes, encoding: str, fileName: str):
	assert type(text) is str
	assert type(encodedText) is bytes
	assert encoding is not None
	assert fileName is not None # because compileSavedOnly

	name = '.'.join(os.path.basename(fileName).split('.')[:-1])
	try:
		e, o = cmd(["make", name + '.compile'])
	except Exception as e:
		msg = 'make: ' + exMsg(e)
		return (msg, None, None)

	e = e.decode(encoding)
	o = o.decode(encoding)
	msg = e + o

	eLines = e.count('\n')
	errs = []
	warns = []
	i = eLines
	for l in o.split('\n'):
		l = l.rstrip() + '\n'
		r = _zcLineCol.match(l)
		if r is not None:
			line = int(r.group(3)) - 1
			col = int(r.group(4)) - 1
			pos = (line, col)
			link = (i, pos)
			m = r.group(5)
			errs.append(link)
		i = i + 1

	return (msg, errs, warns)

# example:
# 304	14/3	CRC8.mpas	Syntax error: Expected "end" but "п" found
_pmkpLineCol = re.compile("^(?:[0-9]+)\t([0-9]+)/([0-9]+)\t([^\t]+)\t([^\n]+)\n")

def mikroPascalCompile (text: str, encodedText: bytes, encoding: str, fileName: str):
	assert type(text) is str
	assert type(encodedText) is bytes
	assert encoding is not None
	assert fileName is not None # because compileSavedOnly

	name = '.'.join(os.path.basename(fileName).split('.')[:-1])
	try:
		e, o = cmd(["make", "CURDIR=" + os.path.realpath(os.curdir), name + '.compile'])
	except Exception as e:
		msg = 'make: ' + exMsg(e)
		return (msg, None, None)

	e = e.decode(encoding)
	o = o.replace(b'\xff', b'').decode(encoding)
	msg = e + o

	eLines = e.count('\n')
	errs = []
	warns = []
	i = eLines
	for l in o.split('\n'):
		r = _pmkpLineCol.match(l + '\n')
		if (r is not None) and (r.group(3) == os.path.basename(fileName)):
			line = int(r.group(1)) - 1
			col = int(r.group(2)) - 1
			pos = (line, col)
			link = (i, pos)
			m = r.group(4)
			if m.startswith('Hint: '):
				pass
			else:
				errs.append(link)
		i = i + 1
	return (msg, errs, warns)

_pmockaLineCol = re.compile("^([0-9]+)\,([0-9]+): ([^\n]+)\n")

def mockaCompile (text: str, encodedText: bytes, encoding: str, fileName: str):
	assert type(text) is str
	assert type(encodedText) is bytes
	assert encoding is not None
	assert fileName is not None # because compileSavedOnly

	name = '.'.join(os.path.basename(fileName).split('.')[:-1])
	try:
		e, o = cmd(["mocka", "-c", name])
	except Exception as e:
		msg = 'mocka: ' + exMsg(e)
		return (msg, None, None)

	e = e.decode(encoding)
	o = o.decode(encoding)
	msg = e + o

	eLines = e.count('\n')
	errs = []
	i = eLines
	for l in o.split('\n'):
		r = _pmockaLineCol.match(l + '\n')
		if r is not None:
			line = int(r.group(1)) - 1
			col = int(r.group(2)) - 1
			pos = (line, col)
			link = (i, pos)
			errs.append(link)
		i = i + 1
	return (msg, errs, None)

_pobcLine = re.compile("^\"([^\"]+)\"\, line ([0-9]+): ([^\n]+)\n")

def obcCompile (text: str, encodedText: bytes, encoding: str, fileName: str):
	assert type(text) is str
	assert type(encodedText) is bytes
	assert encoding is not None
	assert fileName is not None # because compileSavedOnly

	try:
		e, o = cmd(["obc", "-c", fileName])
	except Exception as e:
		msg = 'obc: ' + exMsg(e)
		return (msg, None, None)

	e = e.decode(encoding)
	o = o.decode(encoding)
	msg = e + o

	errs = []
	warns = []
	i = 0
	st = 0; i1 = None
	ll = []
	for l in e.split('\n'):
		if st == 0: # outside
			if l.startswith('"'):
				st = 1
				i1 = i
				ll = [ l ]
		elif st == 1: # inside
			if l.startswith('>'):
				st = 0
				r = _pobcLine.match(' '.join(ll) + '\n')
				if r is not None:
					fName = r.group(1)
					# assert fName == fileName
					line = int(r.group(2)) - 1
					col = 0
					pos = (line, col)
					m = r.group(3)
					for j in xrange(len(ll)):
						link = (i1 + j, pos)
						if m.startswith('warning'):
							warns.append(link)
						else:
							errs.append(link)
			else:
				ll.append( l )
		i = i + 1
	return (msg, errs, warns)

_pxcLineCol = re.compile('\* \[([^ ]+) ([0-9]+)\.([0-9]+) [A-Z][0-9]+\]\n')

def xcmCompile (xCmd: str, text: str, encodedText: bytes, encoding: str, fileName: str | None, suffix: str):
	assert type(text) is str
	assert type(encodedText) is bytes
	assert encoding is not None

	fd, name = tempfile.mkstemp(suffix=suffix)
	try:
		try:
			try:
				os.write(fd, encodedText.replace(b'\t', b' '))
			except Exception as e:
				msg = tr('#File write error') + ': ' + exMsg(e)
				return (msg, None, None)
		finally:
			try:
				os.close(fd)
			except:
				pass
		try:
			e, o = cmd([xCmd, "=compile", name, '+CHANGESYM'])
		except Exception as e:
			msg = xCmd + ': ' + exMsg(e)
			return (msg, None, None)
	finally:
		try:
			os.remove(name)
		except:
			pass

	e = e.decode(encoding)
	o = o.decode(encoding)
	msg = e + o

	eLines = e.count('\n')
	errs = []
	i = eLines
	for l in o.split('\n'):
		r = _pxcLineCol.match(l + '\n')
		if r is not None:
			if r.group(1) == name:
				line = int(r.group(2)) - 1
				col = int(r.group(3)) - 1
				pos = (line, col)
				link = (i, pos)
				errs.append(link)
		i = i + 1
	return (msg, errs, None)

def xcCompileM2 (text, encodedText, encoding, fileName):
	return xcmCompile('xc', text, encodedText, encoding, fileName, '.mod')

def xcCompileO2 (text, encodedText, encoding, fileName):
	return xcmCompile('xc', text, encodedText, encoding, fileName, '.ob2')

def xmCompileM2 (text, encodedText, encoding, fileName):
	return xcmCompile('xm', text, encodedText, encoding, fileName, '.mod')

def xmCompileO2 (text, encodedText, encoding, fileName):
	return xcmCompile('xm', text, encodedText, encoding, fileName, '.ob2')

pyNormalizeNewlinesStr = lambda text: text.replace('\r\n', '\n').replace('\r', '\n')
pyNormalizeNewlinesBytes = lambda encodedText: encodedText.replace(b'\r\n', b'\n').replace(b'\r', b'\n')

def pyCompile (text: str, encodedText: bytes, encoding: None, fileName: str | None):
	assert type(text) is str
	assert type(encodedText) is bytes
	assert encoding is None

	try:
		compile(
			pyNormalizeNewlinesBytes(encodedText),
			'', 'exec')
	except SyntaxError as e:
		msg = e.msg
		pos = ( e.lineno - 1, e.offset - 1 )
		link = (0, pos)
		return (msg, ( link, ), None)
	else:
		return ('', None, None) # ok

# see http://docs.python.org/reference/lexical_analysis.html#encoding-declarations
_cPb = re.compile(b'^[^#]*#.*coding[=:]\s*([-\w.]+)')
_cPs = re.compile('^[^#]*#.*coding[=:]\s*([-\w.]+)')

def pyCoding (x) -> str | None:
	assert type(x) in (str, bytes)

	if type(x) is bytes:
		for line in pyNormalizeNewlinesBytes(x).split(b'\n')[:2]:
			r = _cPb.match(line)
			if r is not None:
				encoding = r.group(1).decode('ascii')
				if Trace: print('pyCoding:', encoding)
				try:
					x = b''.decode(encoding)
				except LookupError:
					print('invalid encoding:', repr(encoding))
					return None
				else:
					return encoding
		else:
			return None
	else:
		for line in pyNormalizeNewlinesStr(x).split('\n')[:2]:
			r = _cPs.match(line)
			if r is not None:
				encoding = r.group(1)
				if Trace: print('pyCoding:', encoding)
				try:
					x = b''.decode(encoding)
				except LookupError:
					print('invalid encoding:', repr(encoding))
					return None
				else:
					return encoding
		else:
			return None

def pyImport (encodedText: bytes) -> str:
	assert type(encodedText) is bytes

	encoding = pyCoding(encodedText)
	if encoding is None:
		if encodedText.startswith(b'\xef\xbb\xbf'):
			encodedText = encodedText[3:]
			encoding = 'utf-8'
		else:
			# encoding = locale.getpreferredencoding()
			encoding = 'utf-8'

	if Trace: print('pyImportEncoding:', encoding)
	return encodedText.decode(encoding)

def pyExport (text: str) -> bytes:
	assert type(text) is str

	encoding = pyCoding(text)
	if encoding is None:
		try:
			x = text.encode('ascii')
		except UnicodeEncodeError:
			if Trace: print('pyExportEncoding: utf-8')
			return b'\xef\xbb\xbf' + text.encode('utf-8')
		else:
			if Trace: print('pyExportEncoding: ascii')
			return x
	else:
		if Trace: print('pyExportEncoding:', encoding)
		return text.encode(encoding)

_pLuaLine = re.compile('^luac-(?:[1-9][0-9\.]*): stdin:([1-9][0-9]*): ([^\n]+)\n')

def luaCompile (text: str, encodedText: bytes, encoding: str, fileName: str | None):
	assert type(text) is str
	assert type(encodedText) is bytes
	assert encoding is not None

	args = ["luac-5.1", "-p", "-"]

	close_fds = not mswindows
	try:
		p = subprocess.Popen(args, bufsize=8192, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=close_fds)
	except Exception as e:
		msg = 'luac-5.1: ' + exMsg(e)
		return (msg, None, None)

	o, e = p.communicate(encodedText)

	e = e.decode(encoding)
	o = o.decode(encoding)
	msg = e + o

	r = _pLuaLine.match(e)
	if r is not None:
		line = int(r.group(1)) - 1
		pos = (line, None)
		link = (0, pos)
		return (msg, ( link, ), None)
	else:
		return (msg, None, None)

def umbrielCompile (text: str, encodedText: bytes, encoding: str, fileName: str | None):
	assert type(text) is str
	assert type(encodedText) is bytes
	assert encoding is not None

	return cocodrivers.toCompileResult( cocodrivers.Umbriel.Process(text) )

def oberon0Compile (text: str, encodedText: bytes, encoding: str, fileName: str | None):
	assert type(text) is str
	assert type(encodedText) is bytes
	assert encoding is not None

	return cocodrivers.toCompileResult( cocodrivers.Oberon0.Process(text) )

_ppyCocoLineCol = re.compile("^file ([^ ]+) : \(([0-9]+), ([0-9]+)\) (.+)$")

def pyCocoCompile (text: str, encodedText: bytes, encoding: str, fileName: str | None):
	assert type(text) is str
	assert type(encodedText) is bytes
	assert encoding is not None

	xCmd = "cocopy"
	# cocopy requirements: atg file must be in current directory

	fd, name = tempfile.mkstemp(dir=".")
	bName = os.path.basename(name)
	try:
		try:
			try:
				os.write(fd, encodedText)
			except Exception as e:
				msg = tr('#File write error') + ': ' + exMsg(e)
				return (msg, None, None)
		finally:
			try:
				os.close(fd)
			except:
				pass
		try:
			e, o = cmd([xCmd, "-t", bName])
		except Exception as e:
			msg = xCmd + ': ' + exMsg(e)
			return (msg, None, None)
	finally:
		try:
			os.remove(name)
		except:
			pass

	e = e.decode(encoding)
	o = o.decode(encoding)

	eLines = e.count('\n')
	errs = []
	warns = []
	i = eLines
	msg = [ e ]
	for line in o.split('\n'):
		r = _ppyCocoLineCol.match(line)
		if (r is not None) and (r.group(1) == bName):
			line = int(r.group(2)) - 1
			col = int(r.group(3)) - 1
			pos = (line, col)
			link = (i, pos)
			errs.append(link)
			msg.append( "%s\n" % (r.group(4),) )
		else:
			msg.append(line + '\n')
		i = i + 1
	return (''.join(msg), errs, warns)

_pocamlLineCol = re.compile("^File \"([^\"]+)\"\, line ([0-9]+), characters ([0-9]+)\-([0-9]+):\n")

def ocamlCompile (text: str, encodedText: bytes, encoding: str, fileName: str):
	assert type(text) is str
	assert type(encodedText) is bytes
	assert encoding is not None
	assert fileName is not None # because compileSavedOnly

	try:
		e, o = cmd(["ocamlc", "-c", fileName])
	except Exception as e:
		msg = 'ocamlc: ' + exMsg(e)
		return (msg, None, None)

	e = e.decode(encoding)
	o = o.decode(encoding)
	msg = e + o

	r = _pocamlLineCol.match(e)
	if r is not None:
		line = int(r.group(2)) - 1
		col = int(r.group(3)) - 1
		pos = (line, col)
		link = (0, pos)
		return (msg, ( link, ), None)
	else:
		return (msg, None, None)

def iverilogCompile (text: str, encodedText: bytes, encoding: str, fileName: str | None):
	assert type(text) is str
	assert type(encodedText) is bytes
	assert encoding is not None

	# TODO

	return ('not implemented', None, None)

def gvhdlCompile (text: str, encodedText: bytes, encoding: str, fileName: str | None):
	assert type(text) is str
	assert type(encodedText) is bytes
	assert encoding is not None

	# TODO

	return ('not implemented', None, None)

#_ppdflatexLine = re.compile("^([^:]+):([0-9]+): (.+)\.$")
#
#def latexCompile (text: str, encodedText: bytes, encoding: str, fileName: str):
#	assert type(text) is str
#	assert type(encodedText) is bytes
#	assert encoding is not None
#	assert fileName is not None # because compileSavedOnly
#
#	try:
#		e, o = cmd(["pdflatex", "-file-line-error", "-interaction", "nonstopmode", fileName])
#	except Exception as e:
#		msg = "pdflatex: " + exMsg(e)
#		return (msg, None, None)
#
#	e = e.decode(encoding)
#	o = o.decode(encoding)
#	msg = e + o
#
#	warns = []
#	errs = []
#	i = 0
#	for line in msg.split('\n'):
#		r = _ppdflatexLine.match(line)
#		if r is not None:
#			line = int(r.group(2)) - 1
#			pos = (line, 0)
#			link = (i, pos)
#			errs.append(link)
#		i = i + 1
#	return (msg, errs, warns)

def winEncoding ():
	if mswindows:
		return locale.getpreferredencoding()
	else:
		return winenc.getByLocale( locale.getdefaultlocale()[0] )

def modObEmpty (name):
	if name is None:
		text = 'MODULE ;\n\n\t(*\n\t\t\n\t*)\n\n\t\n\nEND .\n'
		line = 0
		col = 7
	else:
		text = 'MODULE %s;\n\n\t(*\n\t\t\n\t*)\n\n\t\n\nEND %s.\n' % (name, name)
		line = 3
		col = 2
	return (text, line, col)

def cocoPyAtgEmpty (name):
	if name is None:
		text = 'COMPILER \n\n\t/*\n\t\t\n\t*/\n\nCHARACTERS\n\nTOKENS\n\nCOMMENTS\n\tFROM  TO \n\nIGNORE\n\nPRODUCTIONS\n\n\t =  .\n\nEND .'
		line = 0
		col = 9
	else:
		text = 'COMPILER %s\n\n\t/*\n\t\t\n\t*/\n\nCHARACTERS\n\nTOKENS\n\nCOMMENTS\n\tFROM  TO \n\nIGNORE\n\nPRODUCTIONS\n\n\t%s =  .\n\nEND %s.' % (name, name, name)
		line = 3
		col = 2
	return (text, line, col)

def modZnEmpty (name):
	if name is None:
		text = 'module ;\n\nend .'
		line = 0
		col = 7
	else:
		text = 'module %s;\n\n\n\nend %s.' % (name, name)
		line = 2
		col = 0
	return (text, line, col)

def delphiEmpty (name):
	if name is None:
		text = 'unit ;\n\n(*\n\t\n*)\n\n(* {$OVERFLOWCHECKS ON} *)\n{$RANGECHECKS ON}\n\ninterface\n\n\n\nimplementation\n\n\n\nend.'
		line = 0
		col = 5
	else:
		text = 'unit %s;\n\n(*\n\t\n*)\n\n(* {$OVERFLOWCHECKS ON} *)\n{$RANGECHECKS ON}\n\ninterface\n\n\n\nimplementation\n\n\n\nend (* %s *).' % (name, name)
		line = 3
		col = 1
	return (text, line, col)

vocO2 = {
	'name': 'voc/Oberon-2', # display
	'lang': 'oberon', # gtksourceview
	'style': ('strict',), # gtksourceview
	'extensions': ('Mod', 'mod'),
	'compile': vocO2Compile,
	'empty': modObEmpty,
}

vocOC = {
	'name': 'voc/Component Pascal', # display
	'lang': 'oberon', # gtksourceview
	'style': ('strict',), # gtksourceview
	'extensions': ('Mod', 'mod'),
	'compile': vocOCCompile,
	'empty': modObEmpty,
}

oo2c = {
	'name': 'oo2c/Oberon-2', # display
	'lang': 'oberon', # gtksourceview
	'style': ('strict',), # gtksourceview
	'extensions': ('Mod',),
	'compile': oo2cCompile,
	'empty': modObEmpty,
}

c = {
	'name': 'make/C',
	'lang': 'c', # gtksourceview
	'extensions': ('c',),
	'compile': cCompile,
	'compileSavedOnly': True, # because compile with make
	'empty': ('int main (int argc, char* argv[])\n{\n\t\n\n\treturn 0;\n}\n', 2, 1),
}

cxx = {
	'name': 'make/C++',
	'lang': 'cpp', # gtksourceview
	'extensions': ('cxx', 'cpp'),
	'compile': cCompile, # because compile with make
	'compileSavedOnly': True,
}

zc = {
	'name': 'zc/Zonnon',
	'lang': 'zonnon', # gtksourceview
	'style': ('kate',), # gtksourceview
	'extensions': ('znn',),
	'compile': zcCompile,
	'compileSavedOnly': True, # because compile with make
	'preferredFileEncoding': winEncoding(),
	'empty': modZnEmpty,
}

xcM2 = {
	'name': 'XDS/Modula-2',
	'lang': 'oberon', # gtksourceview
	'style': ('strict',), # gtksourceview
	'extensions': ('mod',),
	'compile': xcCompileM2,
	'empty': modObEmpty,
}

xcO2 = {
	'name': 'XDS/Oberon-2',
	'lang': 'oberon', # gtksourceview
	'style': ('strict',), # gtksourceview
	'extensions': ('ob2',),
	'compile': xcCompileO2,
	'empty': modObEmpty,
}

xmM2 = {
	'name': 'XDS-C/Modula-2',
	'lang': 'oberon', # gtksourceview
	'style': ('strict',), # gtksourceview
	'extensions': ('mod',),
	'compile': xmCompileM2,
	'empty': modObEmpty,
}

xmO2 = {
	'name': 'XDS-C/Oberon-2',
	'lang': 'oberon', # gtksourceview
	'style': ('strict',), # gtksourceview
	'extensions': ('ob2',),
	'compile': xmCompileO2,
	'empty': modObEmpty,
}

python = {
	'name': 'Python',
	'lang': 'python', # gtksourceview
	'style': ('kate',), # gtksourceview
	'extensions': ('py', 'pyw'),
	'compile': pyCompile,
	'import': pyImport,
	'export': pyExport,
	'empty': ("#! /usr/bin/env python\n# -*- coding: %s -*-\n\ndef main ():\n\t\n\nif __name__ == '__main__':\n\tmain()\n" % (locale.getpreferredencoding().lower()), 0, 22),
	'sharpComments': True,
}

lua = {
	'name': 'luac-5.1/Lua',
	'lang': 'lua', # gtksourceview
	'extensions': ('lua',),
	'compile': luaCompile,
}

dcc32 = {
	'name': 'dcc32/Delphi7',
	'lang': 'pascal', # gtksourceview
	'extensions': ('pas', 'dpr'),
	'compile': dcc32Compile,
	'preferredFileEncoding': winEncoding(),
	'empty': delphiEmpty,
	'lineSep': '\r\n', # не обязательно
}

fpc = {
	'name': 'fpc/Borland Pascal 7',
	'lang': 'pascal', # gtksourceview
	'extensions': ('pas',),
	'compile': fpcCompile,
#	'preferredFileEncoding': winEncoding(),
	'empty': delphiEmpty,
#	'lineSep': '\r\n', # не обязательно
}

astrobeLPC2000 = {
	'name': 'Astrobe-LPC2000/Oberon-07',
	'lang': 'oberon', # gtksourceview
	'style': ('strict',), # gtksourceview
	'extensions': ('mod',),
	'compile': astrobeCompileLPC2000,
	'preferredFileEncoding': winEncoding(),
	'empty': modObEmpty,
	'lineSep': '\r\n', # не обязательно
}

astrobeM3 = {
	'name': 'Astrobe-M3/Oberon-07',
	'lang': 'oberon', # gtksourceview
	'style': ('strict',), # gtksourceview
	'extensions': ('mod',),
	'compile': astrobeCompileM3,
	'preferredFileEncoding': winEncoding(),
	'empty': modObEmpty,
	'lineSep': '\r\n', # не обязательно
}

astrobeM4 = {
	'name': 'Astrobe-M4/Oberon-07',
	'lang': 'oberon', # gtksourceview
	'style': ('strict',), # gtksourceview
	'extensions': ('mod',),
	'compile': astrobeCompileM4,
	'preferredFileEncoding': winEncoding(),
	'empty': modObEmpty,
	'lineSep': '\r\n', # не обязательно
}

gpcp = {
	'name': 'gpcp/Component Pascal',
	'lang': 'oberon', # gtksourceview
	'style': ('strict',), # gtksourceview
	'extensions': ('cp',),
	'compile': gpcpCompile,
	'empty': modObEmpty,
	'lineSep': '\r\n', # не обязательно
}

mocka = {
	'name': 'Mocka/Modula-2',
	'lang': 'oberon', # gtksourceview
	'style': ('strict',), # gtksourceview
	'extensions': ('mi',),
	'compile': mockaCompile,
	'compileSavedOnly': True, # because strict filename format
	'empty': modObEmpty,
}

mikroPascal = {
	'name': 'mikroPascal',
	'lang': 'pascal', # gtksourceview
	'extensions': ('mpas',),
	'compile': mikroPascalCompile,
	'compileSavedOnly': True, # because compile with make
	'preferredFileEncoding': winEncoding(),
}

obc = {
	'name': 'obc/Oberon-2',
	'lang': 'oberon', # gtksourceview
	'style': ('strict',), # gtksourceview
	'extensions': ('m',),
	'compile': obcCompile,
	'compileSavedOnly': True, # because strict filename format
	'empty': modObEmpty,
}

dev0 = {
	'name': 'BlackBox/Component Pascal',
	'lang': 'oberon', # gtksourceview
	'style': ('strict',), # gtksourceview
	'extensions': ('txt',),
	'compile': dev0Compile,
	'empty': modObEmpty,
}

ocaml = {
	'name': 'ocamlc/OCaml',
	'lang': 'objective-caml', # gtksourceview
	'style': ('kate',), # gtksourceview
	'extensions': ('ml', 'mli'),
	'compile': ocamlCompile,
	'compileSavedOnly': True, # may be optimized?
}

genie = {
	'name': 'make/genie',
	'lang': 'genie', # gtksourceview
	'style': ('kate',), # gtksourceview
	'extensions': ('gs',),
	'compile': genieCompile,
	'compileSavedOnly': True, # because compile with make
}

iverilog = {
	'name': 'iverilog/Verilog',
	'lang': 'verilog', # gtksourceview
	'style': ('kate',), # gtksourceview
	'extensions': ('v',),
	'compile': iverilogCompile,
	'compileSavedOnly': False,
}

gvhdl = {
	'name': 'gvhdl/VHDL',
	'lang': 'vhdl', # gtksourceview
	'style': ('kate',), # gtksourceview
	'extensions': ('vhdl', 'vhd'),
	'compile': gvhdlCompile,
	'compileSavedOnly': False,
}

# test
umbriel = {
	'name': 'Umbriel',
	'lang': 'oberon', # gtksourceview
	'style': ('strict',), # gtksourceview
	'extensions': ('umb',),
	'compile': umbrielCompile,
	'empty': modObEmpty,
	'lineSep': '\n',
}

oberon0 = {
	'name': 'Oberon-0',
	'lang': 'oberon', # gtksourceview
	'style': ('strict',), # gtksourceview
	'extensions': ('ob0',),
	'compile': oberon0Compile,
	'empty': modObEmpty,
	'lineSep': '\n',
}

pyCoco = {
	'name': 'py-coco',
	# 'style': ('strict',), # gtksourceview
	'extensions': ('atg', 'ATG'),
	'compile': pyCocoCompile,
	'empty': cocoPyAtgEmpty,
}

#latex = {
#	'name': 'pdflatex/LaTeX',
#	'lang': 'latex', # gtksourceview
#	'style': ('tango', 'kate', 'classic'), # gtksourceview
#	'extensions': ('tex',),
#	'compile': cCompile,
#	'compileSavedOnly': True, # FIXME
#	'compile': latexCompile,
#	'empty': '', # FIXME
#}

profiles = (
	vocO2, vocOC, oo2c, obc, astrobeLPC2000, astrobeM3, astrobeM4, gpcp, zc, xcO2, xmO2, xcM2, xmM2, mocka, mikroPascal,
	dcc32, fpc,
	python, lua,
	genie,
	ocaml,
	c, cxx,
	umbriel, oberon0,
	pyCoco,
#	latex,
	dev0,
	iverilog, gvhdl,
)

def test ():
	print(cmdPollOnly(['winepath', '-w', '111']))

if __name__ == '__main__':
	test()
