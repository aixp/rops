# Alexander Shiryaev, 2010

Trace = True

def getSelLines (buffer):
	bounds = buffer.get_selection_bounds()
	if bounds != ():
		startIt, endIt = bounds
		startLine = startIt.get_line()
		endLine = endIt.get_line()
		endCol = endIt.get_line_offset()
		if endCol == 0: endLine = endLine - 1
		if Trace: print(startLine, endLine)
		assert startLine >= 0
		assert endLine >= 0
		assert startLine <= endLine
		return startLine, endLine
	else:
		return None

def shiftLeft (buffer, char):
	assert char != chr(0)

	r = getSelLines(buffer)
	if r != None:
		startLine, endLine = r
		buffer.begin_user_action()
		i = startLine
		while i <= endLine:
			start = buffer.get_iter_at_line(i)
			x = start.get_char().decode('utf-8')
			if x == char:
				end = buffer.get_iter_at_line_offset(i, 1)
				buffer.delete(start, end)
			i = i + 1
		buffer.end_user_action()

		start = buffer.get_iter_at_line(startLine)
		end = buffer.get_iter_at_line(endLine+1)
		buffer.select_range(start, end)

def shiftRight (buffer, char, forceInsert):
	assert char != chr(0)

	r = getSelLines(buffer)
	if r != None:
		startLine, endLine = r
		buffer.begin_user_action()
		i = startLine
		while i <= endLine:
			start = buffer.get_iter_at_line(i)
			if forceInsert or (start.get_char().decode('utf-8') != '\n'):
				buffer.insert(start, char)
			i = i + 1
		buffer.end_user_action()

		start = buffer.get_iter_at_line(startLine)
		end = buffer.get_iter_at_line(endLine+1)
		buffer.select_range(start, end)

def calcMinIndent (buffer, startLine, endLine):
	assert startLine <= endLine

	minIndent = None
	i = startLine
	while i <= endLine:
		start = buffer.get_iter_at_line(i)

		indent = 0
		c = start.get_char()
		while c == '\t':
			indent = indent + 1
			start.forward_char()
			c = start.get_char()

		if c != '\n': # line not empty
			if (minIndent == None) or (minIndent > indent):
				minIndent = indent

		i = i + 1

	if minIndent == None: # all lines is empty
		minIndent = 0

	return minIndent

def sharpComment (buffer):
	r = getSelLines(buffer)
	if r != None:
		startLine, endLine = r

		indent = calcMinIndent(buffer, startLine, endLine)
		print('indent:', indent)

		buffer.begin_user_action()
		i = startLine
		while i <= endLine:
			start = buffer.get_iter_at_line(i)
			if start.get_char() == '\n': # empty line
				buffer.insert(start, '\t' * indent + '#')
			else:
				start.forward_chars(indent)
				buffer.insert(start, '#')
			i = i + 1
		buffer.end_user_action()

		start = buffer.get_iter_at_line(startLine)
		end = buffer.get_iter_at_line(endLine+1)
		buffer.select_range(start, end)

def sharpUnComment (buffer):
	r = getSelLines(buffer)
	if r != None:
		startLine, endLine = r

		buffer.begin_user_action()
		i = startLine
		while i <= endLine:
			start = buffer.get_iter_at_line(i)
			lineStart = start.copy()

			c = start.get_char()
			while c == '\t':
				start.forward_char()
				c = start.get_char()

			if c == '#':
				end = start.copy()
				end.forward_char()
				if end.get_char() == '\n': # empty commented line
					buffer.delete(lineStart, end)
				else: # line not empty
					# if space after sharp, delete it too
					if end.get_char() == ' ':
						end.forward_char()
					buffer.delete(start, end)

			i = i + 1
		buffer.end_user_action()

		start = buffer.get_iter_at_line(startLine)
		end = buffer.get_iter_at_line(endLine+1)
		buffer.select_range(start, end)
