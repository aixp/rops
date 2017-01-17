#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-
# Alexander Shiryaev, 2010-2017
#
# IMPLEMENTATION NOTES:
#	имена файлов храним в кодировке системы (locale.getpreferredlocale())
#	текст Gtk.TextView храним в unicode

import gi

gi.require_version('GObject', '2.0')
from gi.repository import GObject

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

gi.require_version('Gdk', '3.0')
from gi.repository import Gdk

gi.require_version('Pango', '1.0')
from gi.repository import Pango

try:
	gi.require_version('GtkSource', '3.0')
	from gi.repository import GtkSource
except ImportError:
	print 'gtksourceview module not found => some features will be inaccessible!'
	GTKSV = False
else:
	GTKSV = True

import os, sys, locale, codecs, re
try:
	import chardet
except ImportError:
	print 'chardet module not found => automatic encoding detection will not available!'
	CHARDET = False
else:
	CHARDET = True

import profiles, util, curpos, store, textops
from translate import tr, setLang as setTrLang

Trace = True

mswindows = sys.platform == 'win32'

def fileNameToGtk (fileName):
	assert type(fileName) is str # not unicode
	if mswindows:
		return fileName.decode(locale.getpreferredencoding()).encode('utf-8')
	else:
		return fileName

def fileNameFromGtk (gtkFileName):
	assert type(gtkFileName) is str # not unicode
	if mswindows:
		return gtkFileName.decode('utf-8').encode(locale.getpreferredencoding())
	else:
		return gtkFileName

# return values: None | fileName
def OpenFile (parent):
	dialog = Gtk.FileChooserDialog(title=None,action=Gtk.FileChooserAction.OPEN,
		buttons=(Gtk.STOCK_CANCEL,Gtk.ResponseType.CANCEL,Gtk.STOCK_OPEN,Gtk.ResponseType.OK))
	dialog.set_transient_for(parent)
	dialog.set_default_response(Gtk.ResponseType.OK)
	dialog.set_title(tr('#Open file').encode('utf-8'))

	fAll = Gtk.FileFilter()
	fAll.set_name(tr('#All known').encode('utf-8'))
	fToProf = { fAll: None }
	dialog.add_filter(fAll)
	for prof in profiles.profiles:
		f = Gtk.FileFilter()
		f.set_name(prof['name'])
		for ext in prof['extensions']:
			pattern = '*.' + ext
			f.add_pattern(pattern)
			fAll.add_pattern(pattern)
		dialog.add_filter(f)
		fToProf[f] = prof

	resp = dialog.run()
	if resp == Gtk.ResponseType.OK:
		fileName = fileNameFromGtk( dialog.get_filename() )
		prof = fToProf[dialog.get_filter()]
		if prof == None:
			prof = getProf(dialog, fileName)
			if prof == None:
				res = None
			else:
				res = fileName, prof
		else:
			res = fileName, prof
	elif resp in (Gtk.ResponseType.CANCEL, Gtk.ResponseType.DELETE_EVENT):
		res = None
	else:
		assert False

	dialog.destroy()

	return res

def SaveFile (parent, extensions):
	dialog = Gtk.FileChooserDialog(title=None,action=Gtk.FileChooserAction.SAVE,
		buttons=(Gtk.STOCK_CANCEL,Gtk.ResponseType.CANCEL,Gtk.STOCK_SAVE,Gtk.ResponseType.OK))
	dialog.set_transient_for(parent)
	dialog.set_default_response(Gtk.ResponseType.CANCEL)
	dialog.set_title(tr('#Save file').encode('utf-8'))

	fToPostfix = {}
	for ext in extensions:
		f = Gtk.FileFilter()
		pattern = '*.' + ext
		f.set_name(pattern)
		f.add_pattern(pattern)
		dialog.add_filter(f)
		fToPostfix[f] = '.' + ext

	f = Gtk.FileFilter()
	f.set_name(tr('#All files').encode('utf-8'))
	f.add_pattern('*')
	dialog.add_filter(f)
	fToPostfix[f] = ''

	resp = dialog.run()
	if resp == Gtk.ResponseType.OK:
		postfix = fToPostfix[dialog.get_filter()]
		res = fileNameFromGtk( dialog.get_filename() )
		if not res.endswith(postfix):
			res = res + postfix
	elif resp in (Gtk.ResponseType.CANCEL, Gtk.ResponseType.DELETE_EVENT):
		res = None
	else:
		assert False

	dialog.destroy()

	return res

# return values: 'YES' | 'NO' | 'CANCEL'
def SaveRequest (parent):
	dialog = Gtk.MessageDialog(parent,
		Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
		Gtk.MessageType.QUESTION,
		Gtk.ButtonsType.NONE,
		("%s" % (tr("#Save changes?"),)).encode('utf-8')
	)
	dialog.add_buttons(
		Gtk.STOCK_YES, Gtk.ResponseType.YES,
		Gtk.STOCK_NO, Gtk.ResponseType.NO,
		Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL
	)

	dialog.set_default_response(Gtk.ResponseType.CANCEL)

	resp = dialog.run()

	dialog.destroy()

	return { Gtk.ResponseType.CANCEL: 'CANCEL', Gtk.ResponseType.YES: 'YES', Gtk.ResponseType.NO: 'NO', Gtk.ResponseType.DELETE_EVENT: 'CANCEL' }[resp]

def CanOverwrite (parent, fileName):
	dialog = Gtk.MessageDialog(parent,
		Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
		Gtk.MessageType.WARNING,
		Gtk.ButtonsType.NONE,
		"%s\n%s\n%s. %s" % (
			tr('#File').encode('utf-8'),
			fileName.decode(locale.getpreferredencoding()).encode('utf-8'),
			tr('#already exists').encode('utf-8'),
			tr('#Overwrite file?').encode('utf-8')
		)
	)
	dialog.add_buttons(
		Gtk.STOCK_YES, Gtk.ResponseType.YES,
		Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL
	)

	dialog.set_default_response(Gtk.ResponseType.CANCEL)

	resp = dialog.run()

	dialog.destroy()

	return { Gtk.ResponseType.CANCEL: False, Gtk.ResponseType.YES: True, Gtk.ResponseType.DELETE_EVENT: False }[resp]

def getText (textView):
	buffer = textView.get_buffer()
	start, end = buffer.get_bounds()
	text = buffer.get_text(start, end, False).decode('utf-8')
	return text

def NewSrcTextView ():
	view = Gtk.TextView()
	return view

def NewSrcTextSView ():
	buf = GtkSource.Buffer()
	buf.set_property("highlight-syntax", True)

	view = GtkSource.View( buffer=buf )

	view.set_tab_width(4)
	view.set_auto_indent(True)

	return view

normalizeEncoding = lambda enc: codecs.lookup(enc).name

def decodeText (encodedText, encoding):
	assert type(encodedText) is str
	try:
		text = encodedText.decode(encoding)
	except UnicodeError:
		return None
	except LookupError:
		return None
	else:
		return text

# return values: None | 'CANCEL' | text, encoding, autoDetected
def importText (prof, encodedText, parent):
	assert type(encodedText) is str # not unicode

	if prof.has_key('import'):
		assert prof.has_key('export')
		assert not prof.has_key('preferredFileEncoding')

		text = prof['import'](encodedText)
		# знать кодировку при явном импорте в дальнейшем не нужно,
		# потому что в этом случае экспорт тоже должен быть явным, а для него знать кодировку при импорте не нужно
		encoding = None
		autoDetected = False
	else:
		if prof.has_key('preferredFileEncoding'):
			assert not prof.has_key('export')
			preferredEncoding = prof['preferredFileEncoding']
		else:
			preferredEncoding = locale.getpreferredencoding()

		if Trace: print 'preferredImportEncoding:', preferredEncoding

		text = decodeText(encodedText, preferredEncoding)
		if text != None:
			preferredEncoding = normalizeEncoding(preferredEncoding)
		else:
			preferredEncoding = None

		if CHARDET:
			cd = chardet.detect(encodedText)
			if Trace: print 'autoImportEncoding:', cd
			autoEncoding = cd['encoding']
			if (autoEncoding != None) and (autoEncoding != 'ascii'):
				text1 = decodeText(encodedText, autoEncoding)
				if text1 != None:
					autoEncoding = normalizeEncoding(autoEncoding)
					if text == None:
						text = text1
					del text1
				else:
					if Trace: print 'decoding with autoImportEncoding failed'
					autoEncoding = None
			else:
				autoEncoding = None
		else:
			autoEncoding = None

		if (preferredEncoding == None) and (autoEncoding == None):
			return None # can not detect file encoding
		elif preferredEncoding == None: # autoEncoding != None
			encoding = autoEncoding
			autoDetected = True
		elif autoEncoding == None: # preferredEncoding != None
			encoding = preferredEncoding
			autoDetected = False
		elif preferredEncoding == autoEncoding:
			encoding = preferredEncoding
			autoDetected = False
		else: # both present, but differ
			items = (
				"%s (%s)" % (preferredEncoding, tr("#system encoding")),
				"%s (%s)" % (autoEncoding, tr("#auto-detected encoding"))
			)
			idx = SelectItem(
				parent,
				tr('#Select file encoding'),
				tr('#Name'),
				items
			)
			if idx == None:
				return 'CANCEL'
			else:
				encoding = { 0: preferredEncoding, 1: autoEncoding }[idx]
				text = encodedText.decode(encoding)
				autoDetected = False

		if Trace: print 'importEncoding:', encoding

	assert type(text) is unicode
	return text, encoding, autoDetected

def exportText (mod, text):
	assert type(text) is unicode

	prof = mod['profile']

	if mod['importEncoding'] != None:
		assert not prof.has_key('import')
		assert not prof.has_key('export')

		encoding = mod['importEncoding']
		if Trace: print 'exportEncoding:', encoding, '(=importEncoding)'
		encodedText = text.encode(encoding)
	elif prof.has_key('export'): # expoprt function specified
		assert prof.has_key('import')
		assert not prof.has_key('preferredFileEncoding')

		encodedText = prof['export'](text)
		encoding = None
	elif prof.has_key('preferredFileEncoding'): # preferred file encoding specified
		assert not prof.has_key('import')

		encoding = prof['preferredFileEncoding']
		if Trace: print 'exportEncoding:', encoding
		encodedText = text.encode(encoding)
	else:
		encoding = locale.getpreferredencoding()
		if Trace: print 'exportEncoding:', encoding
		encodedText = text.encode(encoding)
	assert type(encodedText) is str # not unicode
	return encodedText, encoding

def setupBuffer (buffer, langName, styleNames):
	if GTKSV:
		sm = GtkSource.StyleSchemeManager.get_default()
		if styleNames != None:
			for styleName in styleNames:
				style = sm.get_scheme(styleName)
				if style != None:
					break
			else:
				style = None
		else:
			style = sm.get_scheme('classic')
		if Trace:
			if style != None:
				print 'style-scheme:', style.get_name()
			else:
				print 'no style-scheme'
		buffer.set_property("style-scheme", style)

		if langName != None:
			lm = GtkSource.LanguageManager.get_default()
			lang = lm.get_language(langName)
		else:
			lang = None
		if Trace:
			if lang != None:
				print 'language:', lang.get_name()
			else:
				print 'no language'
		buffer.set_property("language", lang)

# return values: None | profile
def SelectProfile (parent, profiles):
	items = []
	for prof in profiles:
		items.append( prof['name'].decode('ascii') )
	idx = SelectItem(parent, tr('#Select profile'), tr('#Name'), items)
	if idx == None:
		return None
	else:
		return profiles[idx]

def SelectItem (parent, title, name, items):
	assert type(title) is unicode
	assert type(name) is unicode

	def on_tv_activate (widget, path, column):
		if Trace: print 'tv activate'
		dialog.response(Gtk.ResponseType.OK)

	dialog = Gtk.Dialog(title=title.encode('utf-8'), parent=parent,
		flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT)
	dialog.add_buttons(
		Gtk.STOCK_OK, Gtk.ResponseType.OK,
		Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL
	)
	if parent == None:
		dialog.set_position(Gtk.WindowPosition.CENTER)

	tv = Gtk.TreeView()
	tv.show()

	listStore = Gtk.ListStore(str)
	tv.set_model(listStore)

	for item in items:
		assert type(item) is unicode
		listStore.append([item.encode('utf-8')])

	col = Gtk.TreeViewColumn(name.encode('utf-8'))
	tv.append_column(col)

	cell = Gtk.CellRendererText()
	col.pack_start(cell, True)
	col.add_attribute(cell, 'text', 0)

	dialog.get_content_area().add(tv)

	tv.connect("row_activated", on_tv_activate)

	resp = dialog.run()
	if resp == Gtk.ResponseType.OK:
		x = tv.get_selection().get_selected()
		model, iter = x
		assert model == listStore
		if iter == None: # gtk @ Ubuntu behavior
			idx = 0
		else:
			path = listStore.get_path(iter)
			idx = path[0]
		resp = idx
	elif resp in (Gtk.ResponseType.CANCEL,Gtk.ResponseType.DELETE_EVENT):
		resp = None
	else:
		assert False

	dialog.destroy()

	return resp

exMsg = lambda e: str(e).decode(locale.getpreferredencoding())

def doCompile (base):
	text = getText(base.srcTextView)
	text = normalizeLineSep(text, base.mod['lineSep'])
	try:
		encodedText, encoding = exportText(base.mod, text)
	except Exception, e:
		base.msg_set( tr('#Text convert error') + ': ' + exMsg(e) )
		return

	bakFileName = None
	if base.mod['profile'].get('compileSavedOnly', False):
		if base.mod['fileName'] == None:
			allow = base.do_save()
		elif base.srcTextView.get_buffer().get_modified():
			bakFileName = os.tempnam(os.path.dirname(os.path.realpath(base.mod['fileName'])), os.path.basename(base.mod['fileName'] + '.'))
			try:
				os.rename(base.mod['fileName'], bakFileName)
			except Exception, e:
				print 'can not rename', base.mod['fileName'], 'to', bakFileName
				msg = tr('#File rename error') + ': ' + exMsg(e)
				base.msg_set(msg)
				allow = False
			else:
				try:
					util.writeFile(base.mod['fileName'], encodedText, sync=False)
				except Exception, e:
					try: # destination file must not exists on rename (Windows)
						os.remove(base.mod['fileName'])
					except:
						pass
					err = []
					try:
						os.rename(bakFileName, base.mod['fileName'])
					except Exception, e1:
						msg2 = "%s (%s): %s" % (tr('#File rename error'), tr('#back'), exMsg(e1))
						err.append(msg2)
					msg1 = tr('#File write error') + ': ' + exMsg(e)
					err.append(msg1)
					err.reverse()
					base.msg_set('\n'.join(err))
					allow = False
				else:
					allow = True
		else:
			allow = True
	else:
		allow = True

	if allow:
		try:
			msg, errs, warns = base.mod['profile']['compile']( text, encodedText, encoding, base.mod['fileName'] )
		finally:
			if bakFileName != None:
				try: # destination file must not exists on rename (Windows)
					os.remove(base.mod['fileName'])
				except:
					pass
				try:
					os.rename(bakFileName, base.mod['fileName'])
				except Exception, e:
					msg1 = "%s (%s): %s" % (tr('#File rename error'), tr('#back'), exMsg(e))
					base.msg_set(msg1)
					return

		assert msg != None
		base.msg_set(msg, errs=errs, warns=warns)

		if (errs != None) and (len(errs) > 0):
			msgLine, pos = errs[0]
			line, col = pos
			setCursorPos(base.srcTextView, line, col)

def getCursorPos (buffer):
	mark = buffer.get_insert()
	it = buffer.get_iter_at_mark(mark)
	return it.get_line(), it.get_line_offset()

def setCursorPos (textView, line, col):
	if (line != None) and (line >= 0):
		buffer = textView.get_buffer()
		it = buffer.get_iter_at_line(line)
		if (col != None) and (col > 0):
			it1 = it.copy()
			it1.forward_to_line_end()
			lineLen = it1.get_line_offset()
			if Trace: print 'lineLen:', lineLen
			if col > lineLen:
				col = lineLen
				if Trace: print 'col:', col
			it.forward_chars(col)
		buffer.place_cursor(it)

		# textView.scroll_to_iter(it, ...) не пользуемся, потому что срабатывает не всегда (см. документацию Gtk.TextView)
		textView.scroll_to_mark(buffer.get_insert(), 0.0, True, xalign=1.0, yalign=0.0)

def restoreCurPos (fileName, textView):
	line, col = curpos.loadCurPos(fileName)
	setCursorPos(textView, line, col)

def saveCurPos (fileName, textView):
	line, col = getCursorPos(textView.get_buffer())
	curpos.saveCurPos(fileName, line, col)

def SelectFont (parent, old):
	dialog = Gtk.FontSelectionDialog(tr('#Select font').encode('utf-8'))
	dialog.set_transient_for(parent)
	if old != None:
		r = dialog.set_font_name(old)
		if Trace: print 'set font name:', r
	resp = dialog.run()
	if resp == Gtk.ResponseType.OK:
		new = dialog.get_font_name()
		if Trace: print 'selected font:', new
	else:
		new = old
	dialog.destroy()
	return new

defaultSettings = { 'font': None }
_settingsStoreName = 'settings'
loadSettings = lambda: store.load(_settingsStoreName, defaultSettings)
saveSettings = lambda settings: store.save(_settingsStoreName, settings)

def translateBuilder (builder):
	for obj in builder.get_objects():
		# делаем так, потому что при попытке получения свойств по крейней мере у SeparatorMenuItem он исчезает (где-то ошибка в Gtk или в PyGtk)
		if type(obj) in (Gtk.Window, Gtk.MenuItem, Gtk.Label, Gtk.Button, Gtk.CheckButton):
			if type(obj) is Gtk.Window:
				label = obj.get_title().decode('utf-8')
			else:
				label = obj.get_property('label').decode('utf-8')
			# print label
			if label.startswith('#'):
				label = tr(label.encode('ascii'))
				if type(obj) is Gtk.Window:
					obj.set_title(label.encode('utf-8'))
				else:
					obj.set_property("label", label.encode('utf-8'))
		elif type(obj) in (Gtk.ImageMenuItem, Gtk.ScrolledWindow, Gtk.SeparatorMenuItem, Gtk.Box, Gtk.Paned, Gtk.MenuBar, Gtk.Statusbar, Gtk.Menu, Gtk.Entry, Gtk.Grid, Gtk.TreeView, Gtk.TreeSelection, Gtk.TextView):
			pass
		else:
			print 'translateBuilder: not match type:', type(obj)

# return values: '\n' | '\r\n' | '\r'
def detectLineSep (text):
	ns = text.count('\n')
	rs = text.count('\r')
	rns = text.count('\r\n')
	ns = ns - rns
	rs = rs - rns
	if Trace: print 'ns:', ns, 'rns:', rns, 'rs:', rs
	if (rns > ns) and (rns > rs):
		return '\r\n'
	elif (rs > ns) and (rs > rns):
		return '\r'
	else:
		return '\n'

# разделить такст на строки (в тексте могут использоваться разные разделители строк)
# похоже совпадает с алгоритмом разделения на строки Gtk.TextView
def splitToLines (text):
	lines = []
	for l in text.split('\r\n'):
		for l1 in re.split( '[\r\n]', l ):
			lines.append(l1)
	return lines

normalizeLineSep = lambda text, lineSep: lineSep.join( splitToLines(text) )

# return values: None | matchStartIter, matchEndIter
def doFind (start, textToFindEncoded, backward, ignoreCase):
	assert type(textToFindEncoded) is str # not unicode

	if ignoreCase:
		buffer = start.get_buffer()
		textToFind = textToFindEncoded.decode('utf-8').lower()
		if backward:
			end = buffer.get_start_iter()
			text = buffer.get_text(end, start, False).decode('utf-8').lower()
			r = text.find(textToFind)
			if r >= 0:
				r1 = r
				while True:
					r = text.find(textToFind, r + 1)
					if r == -1:
						break
					r1 = r
				matchStart = end.copy()
				matchStart.forward_chars(r1)
				matchEnd = matchStart.copy()
				matchEnd.forward_chars( len(textToFind) )
				found = matchStart, matchEnd
			else:
				found = False
		else:
			end = buffer.get_end_iter()
			text = buffer.get_text(start, end, False).decode('utf-8').lower()
			r = text.find(textToFind)
			if r >= 0:
				matchStart = start.copy()
				matchStart.forward_chars(r)
				matchEnd = matchStart.copy()
				matchEnd.forward_chars( len(textToFind) )
				found = matchStart, matchEnd
			else:
				found = None
	else: # not ignore case
		if backward:
			found = start.backward_search(textToFindEncoded, 0, None)
		else:
			found = start.forward_search(textToFindEncoded, 0, None)
	return found

def doPrint (parent, textView, fileName):
	assert type(fileName) is unicode

	def on_begin_print (operation, context, compositor):
		while not compositor.paginate(context):
			pass
		nPages = compositor.get_n_pages()
		operation.set_n_pages(nPages)

	def on_draw_page (operation, context, pageNum, compositor):
		compositor.draw_page(context, pageNum)

	if GTKSV:
		# parent = textView.get_toplevel()
		buffer = textView.get_buffer()

		compositor = GtkSource.PrintCompositor.new_from_view(textView)
		compositor.set_wrap_mode(Gtk.WrapMode.WORD_CHAR) # CHAR | NONE | WORD | WORD_CHAR
		compositor.set_highlight_syntax(True)
		# compositor.set_print_line_numbers(5)

		if fileName == u'':
			compositor.set_print_header(False)
			compositor.set_print_footer(False)
		else:
			# set header and footer
			# %N -- page number, %Q -- number of pages
			# see man 3 strftime (%Y -- year, %m -- month, %d -- day, ...)
			compositor.set_header_format(True, '', fileName, '%N/%Q')
			compositor.set_print_header(True)
			compositor.set_print_footer(False)

		printOp = Gtk.PrintOperation()
		printOp.connect("begin-print", on_begin_print, compositor)
		printOp.connect("draw-page", on_draw_page, compositor)
		res = printOp.run(Gtk.PrintOperationAction.PRINT_DIALOG, parent)

		#if res == Gtk.PrintOperationResult.ERROR:
		#	if Trace: 'print error'
		#else:
		#	if Trace: 'print ok'
	else: # not GTKSV
		print 'gtksourceview module required for printing'

class Application:

################################## Find window ################################

	def on_window2_delete_event (self, widget, data=None):
		if Trace: print 'find window delete event'
		self.on_button6_clicked(widget)
		# return True
		return widget.hide_on_delete()

	def on_menuitem11_activate (self, widget, data=None):
		if Trace: print 'find'
		self.findWindow.show()
		self.findStr.select_region(0, -1) # select all
		self.findStr.grab_focus()
		self.findWindow.present()

	def do_find (self, start, backward):
		textToFindEncoded = self.findStr.get_text()
		if Trace: print 'textToFind:', textToFindEncoded.decode('utf-8').encode(locale.getpreferredencoding())

		if textToFindEncoded != '':
			ignoreCase = self.findIgnCase.get_active()
			if Trace: print 'ignoreCase:', ignoreCase

			found = doFind(start, textToFindEncoded, backward, ignoreCase)

			if found:
				if Trace: print 'found'
				matchStart, matchEnd = found

				buffer = self.srcTextView.get_buffer()
				buffer.place_cursor(matchStart)
				# textView.scroll_to_iter(it, ...) не пользуемся, потому что срабатывает не всегда (см. документацию Gtk.TextView)
				self.srcTextView.scroll_to_mark(buffer.get_insert(), 0.0, True, 0.0, 0.0)

				buffer.select_range(matchStart, matchEnd)

				return matchStart, matchEnd
			else:
				return None
		else:
			return None

	def on_button1_clicked (self, widget, data=None):
		if Trace: print 'find first'

		start = self.srcTextView.get_buffer().get_start_iter()
		r = self.do_find(start, False)

	def find_next (self):
		buffer = self.srcTextView.get_buffer()
		mark = buffer.get_insert()
		it = buffer.get_iter_at_mark(mark)
		backward = self.findRevDir.get_active()
		if backward:
			it.backward_char()
		else:
			it.forward_char()
		return self.do_find(it, backward)

	def on_button2_clicked (self, widget, data=None):
		if Trace: print 'find next'
		r = self.find_next()

	def do_replace (self):
		textToReplEncoded = self.findReplStr.get_text()
		textToReplLen = len(textToReplEncoded.decode('utf-8'))
		if Trace: print 'textToReplace:', textToReplEncoded.decode('utf-8').encode(locale.getpreferredencoding())

		r = self.srcTextView.get_buffer().get_selection_bounds()
		if r != ():
			start, end = r

			startOfs = start.get_offset()

			buffer = self.srcTextView.get_buffer()
			buffer.delete(start, end)
			buffer.insert(start, textToReplEncoded)

			start = buffer.get_iter_at_offset(startOfs)
			end = start.copy()
			end.forward_chars(textToReplLen)

			buffer.select_range(start, end)

			return start, end
		else:
			return None

	def on_button3_clicked (self, widget, data=None):
		if Trace: print 'replace'

		r = self.do_replace()

	def on_button4_clicked (self, widget, data=None):
		if Trace: print 'find and replace'

		if self.find_next() != None:
			r = self.do_replace()

	def on_button5_clicked (self, widget, data=None):
		if Trace: print 'replace all'

		it = self.srcTextView.get_buffer().get_start_iter()
		found = self.do_find(it, False)
		cnt = 0
		while found != None:
			matchStart, matchEnd = found
			start, end = self.do_replace()
			cnt = cnt + 1
			found = self.do_find(end, False)
		if Trace: print cnt, 'replacements done'

	def on_button6_clicked (self, widget, data=None):
		if Trace: print 'close'
		self.findWindow.hide()

	def on_entry1_activate (self, widget, data=None):
		if Trace: print 'findStr entry activate'
		self.on_button2_clicked(widget)

	def on_entry1_key_press_event (self, widget, event):
		# if Trace: print 'on find entry key press:', event
		if event.keyval == Gdk.KEY_Tab:
			# вставляем символ TAB вместо смены фокуса
			pos = widget.get_position()
			widget.insert_text( '\t', position=pos )
			widget.set_position(pos + 1)
			return True

	def on_entry2_key_press_event (self, widget, event):
		# if Trace: print 'on replace entry key press:', event
		if event.keyval == Gdk.KEY_Tab:
			# вставляем символ TAB вместо смены фокуса
			pos = widget.get_position()
			widget.insert_text( '\t', position=pos )
			widget.set_position(pos + 1)
			return True

	def on_window2_key_press_event (self, widget, event):
		# if Trace: print 'on findwin key press:', event
		if event.keyval == Gdk.KEY_Escape:
			self.on_button6_clicked(widget)
			return True

################################### Main window ###############################

	# return values: False | True
	def do_save (self, saveAs=False):
		text = getText(self.srcTextView)

		# normalize line sep and rstrip lines
		text = self.mod['lineSep'].join( [ line.rstrip() for line in splitToLines(text) ] )

		try:
			encodedText, encoding = exportText(self.mod, text)
		except Exception, e:
			self.msg_set( tr('#Text convert error') + ': ' + exMsg(e) )
			return

		if (self.mod['fileName'] == None) or saveAs:
			fileName = SaveFile(self.mainWindow, self.mod['profile']['extensions'])
			if fileName != None:
				if os.path.exists(fileName) and not CanOverwrite(self.mainWindow, fileName):
					return False
			else:
				return False
		else:
			fileName = self.mod['fileName']

		try:
			util.writeFile( fileName, encodedText, sync=True )
		except Exception, e:
			self.msg_set( tr('#File write error') + ': ' + exMsg(e) )
			return False
		else:
			self.srcTextView.get_buffer().set_modified(False)
			# update also importEncoding
			self.mod = {
				'fileName': fileName,
				'modified': False,
				'profile': self.mod['profile'],
				'importEncoding': encoding,
				'lineSep': self.mod['lineSep']
			}
			self.modified_changed()
			return True

	# return values: False | True
	def check_save (self):
		modified = self.srcTextView.get_buffer().get_modified()
		if modified:
			yesNoCancel = SaveRequest(self.mainWindow)
			if Trace: print yesNoCancel
			if yesNoCancel == 'YES':
				return self.do_save()
			elif yesNoCancel == 'NO':
				return True
			elif yesNoCancel == 'CANCEL':
				return False
			else:
				assert False, 'invalid case'
		else:
			return True

	def modified_changed (self):
		if Trace: print 'modified:', self.mod['modified']
		if self.mod['fileName'] == None:
			t = tr('#untitled')
		else:
			t = self.mod['fileName'].decode(locale.getpreferredencoding())
		if self.mod['modified']:
			t = t + '*'
		self.mainWindow.set_title("(%s) %s".encode('utf-8') % (self.mod['profile']['name'], t))

	def do_new (self, prof=None, fileName=None):
		# assert not modified

		if prof == None:
			prof = SelectProfile(self.mainWindow, profiles.profiles)
		if prof != None:
			buffer = self.srcTextView.get_buffer()
			setupBuffer(buffer, prof.get('lang'), prof.get('style'))
			new = prof.get('empty')
			if new != None:
				# new, fileName -> text, line, col
				if type(new) is tuple:
					text, line, col = new
				else:
					if fileName == None:
						name = None
					else:
						name = '.'.join(os.path.basename(fileName).split('.')[:-1]).decode(locale.getpreferredencoding())
					text, line, col = new(name)

				if GTKSV:
					buffer.begin_not_undoable_action()
				assert type(text) is unicode
				buffer.set_text(text.encode('utf-8'))
				if GTKSV:
					buffer.end_not_undoable_action()
				it = buffer.get_iter_at_line_offset(line, col)
				buffer.place_cursor(it)
			else:
				if GTKSV:
					buffer.begin_not_undoable_action()
				buffer.set_text('')
				if GTKSV:
					buffer.end_not_undoable_action()
			buffer.set_modified(False)

			lineSep = prof.get('lineSep', '\n')
			assert lineSep in ('\n', '\r\n', '\r')
			if Trace: print 'lineSep:', repr(lineSep)

			self.mod = {
				'fileName': fileName,
				'modified': False,
				'profile': prof,
				'importEncoding': None,
				'lineSep': lineSep
			}
			self.modified_changed()
			self.msg_set(u'')

			if prof.get('sharpComments', False):
				self.miSharpComment.set_property('visible', True)
				self.miSharpUnComment.set_property('visible', True)
			else:
				self.miSharpComment.set_property('visible', False)
				self.miSharpUnComment.set_property('visible', False)

	def on_new (self, widget, data=None):
		if Trace: print 'new'
		if self.check_save():
			if self.mod['fileName'] != None:
				saveCurPos(self.mod['fileName'], self.srcTextView)
			self.do_new()

	def on_window1_delete_event (self, widget, data=None):
		if Trace: print 'mainwin delete event'
		canClose = self.check_save()
		return not canClose

	def on_window1_destroy (self, widget, data=None):
		if Trace: print 'mainwin destroy'

		if self.mod['fileName'] != None:
			saveCurPos(self.mod['fileName'], self.srcTextView)

		if self.settings['modified']:
			del self.settings['modified']
			saveSettings(self.settings)

		self.findWindow.destroy()

		Gtk.main_quit()

	def on_quit (self, widget, data=None):
		if Trace: print 'on quit'
		if self.check_save():
			self.mainWindow.destroy()

	def do_open (self, fileName, prof):
		# assert not modified

		try:
			encodedText = util.readFile(fileName)
		except Exception, e:
			self.msg_set( tr('#File read error') + ': ' + exMsg(e) )
		else:
			r = importText(prof, encodedText, self.mainWindow)
			if r == None:
				self.msg_set( tr('#Text convert error') )
			elif r == 'CANCEL':
				pass
			else:
				text, encoding, autoDetected = r

				buffer = self.srcTextView.get_buffer()
				setupBuffer(buffer, prof.get('lang'), prof.get('style'))
				if GTKSV:
					buffer.begin_not_undoable_action()
				buffer.set_text( text.encode('utf-8') )
				if GTKSV:
					buffer.end_not_undoable_action()
				buffer.set_modified(False)

				lineSep = prof.get('lineSep', None)
				if lineSep == None:
					lineSep = detectLineSep(text)
				assert lineSep in ('\n', '\r\n', '\r')
				if Trace: print 'lineSep:', repr(lineSep)

				self.mod = {
					'fileName': fileName,
					'modified': False,
					'profile': prof,
					'importEncoding': encoding,
					'lineSep': lineSep
				}
				self.modified_changed()
				if autoDetected:
					msg = '%s: %s: %s' % (tr('#WARNING'), tr('#file encoding was detected automatically'), encoding)
					self.msg_set(msg)
				else:
					self.msg_set(u'')

				if prof.get('sharpComments', False):
					self.miSharpComment.set_property('visible', True)
					self.miSharpUnComment.set_property('visible', True)
				else:
					self.miSharpComment.set_property('visible', False)
					self.miSharpUnComment.set_property('visible', False)

				restoreCurPos(fileName, self.srcTextView)

	def on_open (self, widget, data=None):
		if Trace: print 'open'
		if self.check_save():
			# assert not modified
			r = OpenFile(self.mainWindow)
			if r != None:
				fileName, prof = r
				if Trace: print fileName
				if self.mod['fileName'] != None:
					saveCurPos(self.mod['fileName'], self.srcTextView)
				self.do_open(fileName, prof)

	def on_save (self, widget, data=None):
		if Trace: print 'save'
		r = self.do_save()

	def on_save_as (self, widget, data=None):
		if Trace: print 'save as'
		r = self.do_save(saveAs=True)

	def on_print (self, widget, data=None):
		if Trace: print 'print'

		if self.mod['fileName'] == None:
			fName = u''
		else:
			fName = os.path.basename(self.mod['fileName']).decode(locale.getpreferredencoding())
		doPrint(self.mainWindow, self.srcTextView, fName)

	def on_textview1_expose_event (self, widget, data=None):
		# if Trace: print 'src expose event'
		newModified = self.srcTextView.get_buffer().get_modified()
		if newModified != self.mod['modified']:
			self.mod['modified'] = newModified
			self.modified_changed()

	def on_menuitem3_activate (self, widget, data=None):
	# def on_toolbutton1_clicked (self, widget, data=None):
		if Trace: print 'compile'
		doCompile(self)

	def on_menuitem5_activate (self, widget, data=None):
		if Trace: print 'sharp comment'
		textops.sharpComment(self.srcTextView.get_buffer())

	def on_menuitem6_activate (self, widget, data=None):
		if Trace: print 'sharp uncomment'
		textops.sharpUnComment(self.srcTextView.get_buffer())

	def on_menuitem7_activate (self, widget, data=None):
		if Trace: print 'shift left'
		textops.shiftLeft(self.srcTextView.get_buffer(), '\t')

	def on_menuitem8_activate (self, widget, data=None):
		if Trace: print 'shift right'
		textops.shiftRight(self.srcTextView.get_buffer(), '\t', False)

	def msg_set (self, text, errs=None, warns=None):
		assert type(text) is unicode
		self.msgTextView.get_buffer().set_text(text.encode('utf-8'))

		def addLinks (l, tag):
			if l != None:
				for msgLine, pos in l:
					it1 = msgBuf.get_iter_at_line(msgLine)

					# skip spaces
					#c = it1.get_char()
					#while c in (' ', '\t'):
					#	it1.forward_char()
					#	c = it1.get_char()

					it2 = it1.copy()
					it2.forward_to_line_end()
					msgBuf.apply_tag(tag, it1, it2)

					links[msgLine] = pos

		links = {}
		msgBuf = self.msgTextView.get_buffer()
		addLinks(errs, self.msgErrTag)
		addLinks(warns, self.msgWarnTag)
		self.msgLinks = links

	def on_menuitem10_activate (self, widget, data=None):
		if Trace: print 'select font'
		old = self.settings['font']
		new = SelectFont(self.mainWindow, old)
		if old != new:
			self.settings['font'] = new
			self.settings['modified'] = True
			self.srcTextView.modify_font(Pango.FontDescription(new))

	def on_textview1_key_press_event (self, widget, event):
		if event.keyval == Gdk.KEY_Escape:
			if Trace: print 'ESC'

			buffer = self.srcTextView.get_buffer()
			bounds = buffer.get_selection_bounds()
			if bounds != ():
				startIt, endIt = bounds
				buffer.select_range(startIt, startIt)

	def msg_link_tag_event (self, tag, widget, event, iter):
		if event.type == Gdk.EventType.BUTTON_RELEASE:
			if Trace: print 'msg link tag event btn release'

			msgLine = iter.get_line()
			if Trace: print 'msg line:', msgLine

			pos = self.msgLinks.get(msgLine, None)
			srcLine, srcCol = pos

			if Trace: print 'link to pos:', pos

			setCursorPos(self.srcTextView, srcLine, srcCol)

			def srcTextViewGrabFocus ():
				if Trace: print 'idle src view grab focus'
				self.srcTextView.grab_focus()
				return False

			GObject.idle_add(srcTextViewGrabFocus)

		return False

	def __init__ (self, par):
		self.msgLinks = None

		self.settings = loadSettings()
		self.settings['modified'] = False

		builder = Gtk.Builder()
		# gladeFile = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'ide-gtk3.glade')
		gladeFile = os.path.join( util.dataDir(), 'ide-gtk3.glade' )
		if Trace: print 'gladeFile:', gladeFile
		builder.add_from_file( fileNameToGtk(gladeFile) )
		builder.connect_signals(self)

		self.mainWindow = builder.get_object('window1')

		# http://askubuntu.com/questions/153549/how-to-detect-a-computers-physical-screen-size-in-gtk
		s = self.mainWindow.get_screen()
		m = s.get_monitor_at_window(s.get_active_window())
		monitor = s.get_monitor_geometry(m)
		width = monitor.width
		height = monitor.height

		self.mainWindow.set_property("default_width", width / 2)
		self.mainWindow.set_property("default_height", 4 * height / 5)

		self.miSharpComment = builder.get_object('menuitem5')
		self.miSharpUnComment = builder.get_object('menuitem6')

		if GTKSV:
			view = NewSrcTextSView()
		else:
			view = NewSrcTextView()
		builder.get_object('scrolledwindow1').add(view)
		view.connect("draw", self.on_textview1_expose_event)
		view.connect("key-press-event", self.on_textview1_key_press_event)
		view.set_property("can-focus", True)
		view.set_property("has-focus", True)
		view.show()
		self.srcTextView = view

		if self.settings['font'] != None:
			self.srcTextView.modify_font(Pango.FontDescription(self.settings['font']))

		self.msgTextView = builder.get_object('textview2')
#		color = self.mainWindow.get_visual().alloc_color(
#			65535, 49152, 49152
#		)
		color = 'pink'
		self.msgErrTag = self.msgTextView.get_buffer().create_tag(background=color)
		self.msgErrTag.connect("event", self.msg_link_tag_event)
#		color = self.mainWindow.get_colormap().alloc_color(
#			65535, 65535, 32768
#		)
		color = 'yellow'
		self.msgWarnTag = self.msgTextView.get_buffer().create_tag(background=color)
		self.msgWarnTag.connect("event", self.msg_link_tag_event)

		self.findWindow = builder.get_object('window2')
		self.findWindow.set_transient_for(self.mainWindow)
		self.findWindow.set_keep_above(True)
		self.findStr = builder.get_object('entry1')
		self.findReplStr = builder.get_object('entry2')
		self.findIgnCase = builder.get_object('checkbutton1')
		self.findRevDir = builder.get_object('checkbutton2')

		translateBuilder(builder)

		self.mainWindow.show()

		prof = profiles.profiles[0]
		self.do_new(prof=prof)
		if par == None:
			self.on_new(None)
		else:
			fileName, prof = par
			if os.path.exists(fileName):
				self.do_open(fileName, prof)
			else:
				self.do_new(prof=prof, fileName=fileName)
				self.do_save() # "touch"

	def main (self):
		Gtk.main()

# return values: False | None | prof
# False: can not lookup profile by extension
# None: cancelled
def getProf (parent, fileName):
	if '.' in fileName:
		ext = fileName.split('.')[-1:][0]
		ps = []
		for prof in profiles.profiles:
			for ext1 in prof['extensions']:
				if ext1 == ext:
					ps.append(prof)
		if len(ps) == 1:
			return ps[0]
		elif len(ps) > 0:
			return SelectProfile(parent, ps)
		else:
			return False
	else:
		return False

def main ():
	x = locale.getdefaultlocale()[0]
	if x != None:
		setTrLang( x.split('_')[0] )

	if Gdk.get_display() != None:
		# 4 варианта начала работы:
		# 1) запустили без параметров для создания нового файла
		# 2) запустили без параметров для открытия нового файла
		# 3) запустили для открытия заданного файла
		# 4) запустили для создания заданного файла
		if len(sys.argv) == 2:
			fileName = sys.argv[1]
			prof = getProf(None, fileName)
			if prof == False:
				sys.stderr.write(tr('#can not lookup profile by file extension').encode(locale.getpreferredencoding()) + '\n')
			elif prof != None:
				Application( (fileName, prof) ).main()
		else:
			Application(None).main()
		if Trace: print tr('#all done').encode(locale.getpreferredencoding())

if __name__ == '__main__':
	main()
