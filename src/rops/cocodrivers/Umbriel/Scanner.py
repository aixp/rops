
import sys

unicode = lambda x: x
unichr = chr

class Token( object ):
   def __init__( self ):
      self.kind   = 0     # token kind
      self.pos    = 0     # token position in the source text (starting at 0)
      self.col    = 0     # token column (starting at 0)
      self.line   = 0     # token line (starting at 1)
      self.val    = u''   # token value
      self.next   = None  # AW 2003-03-07 Tokens are kept in linked list


class Position( object ):    # position of source code stretch (e.g. semantic action, resolver expressions)
   def __init__( self, buf, beg, len, col ):
      assert isinstance( buf, Buffer )
      assert isinstance( beg, int )
      assert isinstance( len, int )
      assert isinstance( col, int )

      self.buf = buf
      self.beg = beg   # start relative to the beginning of the file
      self.len = len   # length of stretch
      self.col = col   # column number of start position

   def getSubstring( self ):
      return self.buf.readPosition( self )

class Buffer( object ):
   EOF      = u'\u0100'     # 256

   def __init__( self, s ):
      self.buf    = s
      self.bufLen = len(s)
      self.pos    = 0
      self.lines  = s.splitlines( True )

   def Read( self ):
      if self.pos < self.bufLen:
         result = unichr(ord(self.buf[self.pos]) & 0xff)   # mask out sign bits
         self.pos += 1
         return result
      else:
         return Buffer.EOF

   def ReadChars( self, numBytes=1 ):
      result = self.buf[ self.pos : self.pos + numBytes ]
      self.pos += numBytes
      return result

   def Peek( self ):
      if self.pos < self.bufLen:
         return unichr(ord(self.buf[self.pos]) & 0xff)    # mask out sign bits
      else:
         return Scanner.buffer.EOF

   def getString( self, beg, end ):
      s = ''
      oldPos = self.getPos( )
      self.setPos( beg )
      while beg < end:
         s += self.Read( )
         beg += 1
      self.setPos( oldPos )
      return s

   def getPos( self ):
      return self.pos

   def setPos( self, value ):
      if value < 0:
         self.pos = 0
      elif value >= self.bufLen:
         self.pos = self.bufLen
      else:
         self.pos = value

   def readPosition( self, pos ):
      assert isinstance( pos, Position )
      self.setPos( pos.beg )
      return self.ReadChars( pos.len )

   def __iter__( self ):
      return iter(self.lines)

class Scanner(object):
   EOL     = u'\n'
   eofSym  = 0

   charSetSize = 256
   maxT = 60
   noSym = 60
   start = [
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  9, 29,  0,  0, 28,  8, 19, 20, 26, 23, 15, 24, 33, 27,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 34, 13, 35, 14, 36,  0,
     0,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 16,  0, 18,  0,  0,
     0,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  0, 22,  0, 25,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     -1]


   def __init__( self, s ):
      self.buffer = Buffer( unicode(s) ) # the buffer instance

      self.ch        = u'\0'       # current input character
      self.pos       = -1          # column number of current character
      self.line      = 1           # line number of current character
      self.lineStart = 0           # start position of current line
      self.oldEols   = 0           # EOLs that appeared in a comment;
      self.NextCh( )
      self.ignore    = set( )      # set of characters to be ignored by the scanner
      self.ignore.add( ord(' ') )  # blanks are always white space
      self.ignore.add(9)
      self.ignore.add(10)
      self.ignore.add(11)
      self.ignore.add(12)

      # fill token list
      self.tokens = Token( )       # the complete input token stream
      node   = self.tokens

      node.next = self.NextToken( )
      node = node.next
      while node.kind != Scanner.eofSym:
         node.next = self.NextToken( )
         node = node.next

      node.next = node
      node.val  = u'EOF'
      self.t  = self.tokens     # current token
      self.pt = self.tokens     # current peek token

   def NextCh( self ):
      if self.oldEols > 0:
         self.ch = Scanner.EOL
         self.oldEols -= 1
      else:
         self.ch = self.buffer.Read( )
         self.pos += 1
         # replace isolated '\r' by '\n' in order to make
         # eol handling uniform across Windows, Unix and Mac
         if (self.ch == u'\r') and (self.buffer.Peek() != u'\n'):
            self.ch = Scanner.EOL
         if self.ch == Scanner.EOL:
            self.line += 1
            self.lineStart = self.pos + 1




   def Comment0( self ):
      level = 1
      line0 = self.line
      lineStart0 = self.lineStart
      self.NextCh()
      if self.ch == '*':
         self.NextCh()
         while True:
            if self.ch == '*':
               self.NextCh()
               if self.ch == ')':
                  level -= 1
                  if level == 0:
                     self.oldEols = self.line - line0
                     self.NextCh()
                     return True
                  self.NextCh()
            elif self.ch == '(':
               self.NextCh()
               if self.ch == '*':
                  level += 1
                  self.NextCh()
            elif self.ch == Buffer.EOF:
               return False
            else:
               self.NextCh()
      else:
         if self.ch == Scanner.EOL:
            self.line -= 1
            self.lineStart = lineStart0
         self.pos = self.pos - 2
         self.buffer.setPos(self.pos+1)
         self.NextCh()
      return False


   def CheckLiteral( self ):
      lit = self.t.val
      if lit == "MODULE":
         self.t.kind = 6
      elif lit == "BEGIN":
         self.t.kind = 9
      elif lit == "END":
         self.t.kind = 10
      elif lit == "CONST":
         self.t.kind = 11
      elif lit == "TYPE":
         self.t.kind = 12
      elif lit == "VAR":
         self.t.kind = 13
      elif lit == "ARRAY":
         self.t.kind = 15
      elif lit == "OF":
         self.t.kind = 17
      elif lit == "RECORD":
         self.t.kind = 21
      elif lit == "PROCEDURE":
         self.t.kind = 23
      elif lit == "IF":
         self.t.kind = 27
      elif lit == "THEN":
         self.t.kind = 28
      elif lit == "ELSIF":
         self.t.kind = 29
      elif lit == "ELSE":
         self.t.kind = 30
      elif lit == "CASE":
         self.t.kind = 31
      elif lit == "WHILE":
         self.t.kind = 33
      elif lit == "DO":
         self.t.kind = 34
      elif lit == "REPEAT":
         self.t.kind = 35
      elif lit == "UNTIL":
         self.t.kind = 36
      elif lit == "FOR":
         self.t.kind = 37
      elif lit == "TO":
         self.t.kind = 38
      elif lit == "BY":
         self.t.kind = 39
      elif lit == "LOOP":
         self.t.kind = 40
      elif lit == "EXIT":
         self.t.kind = 41
      elif lit == "RETURN":
         self.t.kind = 42
      elif lit == "NOT":
         self.t.kind = 45
      elif lit == "DIV":
         self.t.kind = 49
      elif lit == "MOD":
         self.t.kind = 50
      elif lit == "AND":
         self.t.kind = 51
      elif lit == "OR":
         self.t.kind = 53


   def NextToken( self ):
      while ord(self.ch) in self.ignore:
         self.NextCh( )
      if (self.ch == '(' and self.Comment0()):
         return self.NextToken()

      apx = 0
      self.t = Token( )
      self.t.pos = self.pos
      self.t.col = self.pos - self.lineStart + 1
      self.t.line = self.line
      state = self.start[ord(self.ch)]
      buf = u''
      buf += unicode(self.ch)
      self.NextCh()

      done = False
      while not done:
         if state == -1:
            self.t.kind = Scanner.eofSym     # NextCh already done
            done = True
         elif state == 0:
            self.t.kind = Scanner.noSym      # NextCh already done
            done = True
         elif state == 1:
            if (self.ch >= '0' and self.ch <= '9'
                 or self.ch >= 'A' and self.ch <= 'Z'
                 or self.ch >= 'a' and self.ch <= 'z'):
               buf += unicode(self.ch)
               self.NextCh()
               state = 1
            else:
               self.t.kind = 1
               self.t.val = buf
               self.CheckLiteral()
               return self.t
         elif state == 2:
            self.t.kind = 2
            done = True
         elif state == 3:

            self.pos = self.pos - apx - 1
            self.line = self.t.line
            self.buffer.setPos(self.pos+1)
            self.NextCh()
            self.t.kind = 3
            done = True
         elif state == 4:
            if (self.ch >= '0' and self.ch <= '9'):
               buf += unicode(self.ch)
               self.NextCh()
               state = 4
            elif (self.ch == 'E'
                 or self.ch == 'e'):
               buf += unicode(self.ch)
               self.NextCh()
               state = 5
            else:
               self.t.kind = 4
               done = True
         elif state == 5:
            if (self.ch >= '0' and self.ch <= '9'):
               buf += unicode(self.ch)
               self.NextCh()
               state = 7
            elif (self.ch == '+'
                 or self.ch == '-'):
               buf += unicode(self.ch)
               self.NextCh()
               state = 6
            else:
               self.t.kind = Scanner.noSym
               done = True
         elif state == 6:
            if (self.ch >= '0' and self.ch <= '9'):
               buf += unicode(self.ch)
               self.NextCh()
               state = 7
            else:
               self.t.kind = Scanner.noSym
               done = True
         elif state == 7:
            if (self.ch >= '0' and self.ch <= '9'):
               buf += unicode(self.ch)
               self.NextCh()
               state = 7
            else:
               self.t.kind = 4
               done = True
         elif state == 8:
            if (ord(self.ch) <= 12
                 or ord(self.ch) >= 14 and self.ch <= '&'
                 or self.ch >= '(' and ord(self.ch) <= 255 or ord(self.ch) > 256):
               buf += unicode(self.ch)
               self.NextCh()
               state = 8
            elif ord(self.ch) == 39:
               buf += unicode(self.ch)
               self.NextCh()
               state = 10
            else:
               self.t.kind = Scanner.noSym
               done = True
         elif state == 9:
            if (ord(self.ch) <= 12
                 or ord(self.ch) >= 14 and self.ch <= '!'
                 or self.ch >= '#' and ord(self.ch) <= 255 or ord(self.ch) > 256):
               buf += unicode(self.ch)
               self.NextCh()
               state = 9
            elif self.ch == '"':
               buf += unicode(self.ch)
               self.NextCh()
               state = 10
            else:
               self.t.kind = Scanner.noSym
               done = True
         elif state == 10:
            self.t.kind = 5
            done = True
         elif state == 11:
            if (self.ch >= '0' and self.ch <= '9'):
               buf += unicode(self.ch)
               self.NextCh()
               state = 11
            elif self.ch == 'C':
               buf += unicode(self.ch)
               self.NextCh()
               state = 2
            elif self.ch == '.':
               apx += 1
               buf += unicode(self.ch)
               self.NextCh()
               state = 12
            else:
               self.t.kind = 3
               done = True
         elif state == 12:
            if (self.ch >= '0' and self.ch <= '9'):
               apx = 0
               buf += unicode(self.ch)
               self.NextCh()
               state = 4
            elif self.ch == '.':
               apx += 1
               buf += unicode(self.ch)
               self.NextCh()
               state = 3
            elif (self.ch == 'E'
                 or self.ch == 'e'):
               apx = 0
               buf += unicode(self.ch)
               self.NextCh()
               state = 5
            else:
               self.t.kind = 4
               done = True
         elif state == 13:
            self.t.kind = 7
            done = True
         elif state == 14:
            self.t.kind = 14
            done = True
         elif state == 15:
            self.t.kind = 16
            done = True
         elif state == 16:
            self.t.kind = 18
            done = True
         elif state == 17:
            self.t.kind = 19
            done = True
         elif state == 18:
            self.t.kind = 20
            done = True
         elif state == 19:
            self.t.kind = 24
            done = True
         elif state == 20:
            self.t.kind = 25
            done = True
         elif state == 21:
            self.t.kind = 26
            done = True
         elif state == 22:
            self.t.kind = 32
            done = True
         elif state == 23:
            self.t.kind = 43
            done = True
         elif state == 24:
            self.t.kind = 44
            done = True
         elif state == 25:
            self.t.kind = 46
            done = True
         elif state == 26:
            self.t.kind = 47
            done = True
         elif state == 27:
            self.t.kind = 48
            done = True
         elif state == 28:
            self.t.kind = 52
            done = True
         elif state == 29:
            self.t.kind = 54
            done = True
         elif state == 30:
            self.t.kind = 55
            done = True
         elif state == 31:
            self.t.kind = 57
            done = True
         elif state == 32:
            self.t.kind = 59
            done = True
         elif state == 33:
            if self.ch == '.':
               buf += unicode(self.ch)
               self.NextCh()
               state = 17
            else:
               self.t.kind = 8
               done = True
         elif state == 34:
            if self.ch == '=':
               buf += unicode(self.ch)
               self.NextCh()
               state = 21
            else:
               self.t.kind = 22
               done = True
         elif state == 35:
            if self.ch == '>':
               buf += unicode(self.ch)
               self.NextCh()
               state = 30
            elif self.ch == '=':
               buf += unicode(self.ch)
               self.NextCh()
               state = 31
            else:
               self.t.kind = 56
               done = True
         elif state == 36:
            if self.ch == '=':
               buf += unicode(self.ch)
               self.NextCh()
               state = 32
            else:
               self.t.kind = 58
               done = True

      self.t.val = buf
      return self.t

   def Scan( self ):
      self.t = self.t.next
      self.pt = self.t.next
      return self.t

   def Peek( self ):
      self.pt = self.pt.next
      while self.pt.kind > self.maxT:
         self.pt = self.pt.next

      return self.pt

   def ResetPeek( self ):
      self.pt = self.t
