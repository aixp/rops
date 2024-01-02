#-------------------------------------------------------------------------
#Parser.py -- ATG file parser
#Compiler Generator Coco/R,
#Copyright (c) 1990, 2004 Hanspeter Moessenboeck, University of Linz
#extended by M. Loeberbauer & A. Woess, Univ. of Linz
#ported from Java to Python by Ronald Longo
#
#This program is free software; you can redistribute it and/or modify it
#under the terms of the GNU General Public License as published by the
#Free Software Foundation; either version 2, or (at your option) any
#later version.
#
#This program is distributed in the hope that it will be useful, but
#WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
#or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
#for more details.
#
#You should have received a copy of the GNU General Public License along
#with this program; if not, write to the Free Software Foundation, Inc.,
#59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
#As an exception, it is allowed to write an extension of Coco/R that is
#used as a plugin in non-free software.
#
#If not otherwise stated, any source code generated by Coco/R (other than
#Coco/R itself) does not fall under the GNU General Public License.
#-------------------------------------------------------------------------*/

import sys

from .Scanner import Token
from .Scanner import Scanner
from .Scanner import Position

Trace = False

class ErrorRec( object ):
   def __init__( self, l, c, s ):
      self.line   = l
      self.col    = c
      self.num    = 0
      self.str    = s


class Errors( object ):
   errMsgFormat = "file %(file)s : (%(line)d, %(col)d) %(text)s\n"
   eof          = False
   count        = 0         # number of errors detected
   fileName     = ''
   listName     = ''
   mergeErrors  = False
   mergedList   = None      # PrintWriter
   errors       = [ ]
   minErrDist   = 2
   errDist      = minErrDist
      # A function with prototype: f( errorNum=None ) where errorNum is a
      # predefined error number.  f returns a tuple, ( line, column, message )
      # such that line and column refer to the location in the
      # source file most recently parsed.  message is the error
      # message corresponging to errorNum.

   @staticmethod
   def Init( fn, dir, merge, getParsingPos, errorMessages ):
      Errors.theErrors = [ ]
      Errors.getParsingPos = getParsingPos
      Errors.errorMessages = errorMessages
      Errors.fileName = fn
      listName = dir + 'listing.txt'
      Errors.mergeErrors = merge
      if Errors.mergeErrors and Trace:
         try:
            Errors.mergedList = open( listName, 'w' )
         except IOError:
            raise RuntimeError( '-- Compiler Error: could not open ' + listName )

   @staticmethod
   def storeError( line, col, s ):
      if Errors.mergeErrors:
         Errors.errors.append( ErrorRec( line, col, s ) )
      else:
         Errors.printMsg( Errors.fileName, line, col, s )

   @staticmethod
   def SynErr( errNum, errPos=None ):
      line,col = errPos if errPos else Errors.getParsingPos( )
      msg = Errors.errorMessages[ errNum ]
      Errors.storeError( line, col, msg )
      Errors.count += 1

   @staticmethod
   def SemErr( errMsg, errPos=None ):
      line,col = errPos if errPos else Errors.getParsingPos( )
      Errors.storeError( line, col, errMsg )
      Errors.count += 1

   @staticmethod
   def Warn( errMsg, errPos=None ):
      line,col = errPos if errPos else Errors.getParsingPos( )
      Errors.storeError( line, col, errMsg )

   @staticmethod
   def Exception( errMsg ):
      print(errMsg)
      assert False

   @staticmethod
   def printMsg( fileName, line, column, msg ):
      vals = { 'file':fileName, 'line':line, 'col':column, 'text':msg }
      sys.stdio.write( Errors.errMsgFormat % vals )

   @staticmethod
   def display( s, e ):
      assert Trace
      Errors.mergedList.write('**** ')
      for c in xrange( 1, e.col ):
         if s[c-1] == '\t':
            Errors.mergedList.write( '\t' )
         else:
            Errors.mergedList.write( ' ' )
      Errors.mergedList.write( '^ ' + e.str + '\n')

   @staticmethod
   def Summarize( sourceBuffer ):
      if Errors.mergeErrors:
         # Initialize the line iterator
         srcLineIter = iter(sourceBuffer)
         srcLineStr  = next(srcLineIter)
         srcLineNum  = 1

         try:
            # Initialize the error iterator
            errIter = iter(Errors.errors)
            errRec  = next(errIter)

            # Advance to the source line of the next error
            while srcLineNum < errRec.line:
               if Trace:
                   Errors.mergedList.write( '%4d %s\n' % (srcLineNum, srcLineStr) )

               srcLineStr = next(srcLineIter)
               srcLineNum += 1

            # Write out all errors for the current source line
            while errRec.line == srcLineNum:
               if Trace:
                  Errors.display( srcLineStr, errRec )

               errRec = next(errIter)
         except:
            pass

         # No more errors to report
         try:
            # Advance to end of source file
            while True:
               Errors.mergedList.write( '%4d %s\n' % (srcLineNum, srcLineStr) )

               srcLineStr = next(srcLineIter)
               srcLineNum += 1
         except:
            pass

         if Trace:
            Errors.mergedList.write( '\n' )
            Errors.mergedList.write( '%d errors detected\n' % Errors.count )
            Errors.mergedList.close( )

      if Trace:
         sys.stdout.write( '%d errors detected\n' % Errors.count )
         if (Errors.count > 0) and Errors.mergeErrors:
            sys.stdout.write( 'see ' + Errors.listName + '\n' )


class Parser( object ):
   _EOF = 0
   _identifier = 1
   _char = 2
   _integer = 3
   _real = 4
   _string = 5
   maxT = 60

   T          = True
   x          = False
   minErrDist = 2


   def __init__( self ):
      self.scanner     = None
      self.token       = None           # last recognized token
      self.la          = None           # lookahead token
      self.genScanner  = False
      self.tokenString = ''             # used in declarations of literal tokens
      self.noString    = '-none-'       # used in declarations of literal tokens
      self.errDist     = Parser.minErrDist

   def getParsingPos( self ):
      return self.la.line, self.la.col

   def SynErr( self, errNum ):
      if self.errDist >= Parser.minErrDist:
         Errors.SynErr( errNum )

      self.errDist = 0

   def SemErr( self, msg ):
      if self.errDist >= Parser.minErrDist:
         Errors.SemErr( msg )

      self.errDist = 0

   def Warning( self, msg ):
      if self.errDist >= Parser.minErrDist:
         Errors.Warn( msg )

      self.errDist = 0

   def Successful( self ):
      return Errors.count == 0;

   def LexString( self ):
      return self.token.val

   def LookAheadString( self ):
      return self.la.val

   def Get( self ):
      while True:
         self.token = self.la
         self.la = self.scanner.Scan( )
         if self.la.kind <= Parser.maxT:
            self.errDist += 1
            break

         self.la = self.token

   def Expect( self, n ):
      if self.la.kind == n:
         self.Get( )
      else:
         self.SynErr( n )

   def StartOf( self, s ):
      return self.set[s][self.la.kind]

   def ExpectWeak( self, n, follow ):
      if self.la.kind == n:
         self.Get( )
      else:
         self.SynErr( n )
         while not self.StartOf(follow):
            self.Get( )

   def WeakSeparator( self, n, syFol, repFol ):
      s = [ False for i in xrange( Parser.maxT+1 ) ]
      if self.la.kind == n:
         self.Get( )
         return True
      elif self.StartOf(repFol):
         return False
      else:
         for i in xrange( Parser.maxT ):
            s[i] = self.set[syFol][i] or self.set[repFol][i] or self.set[0][i]
         self.SynErr( n )
         while not s[self.la.kind]:
            self.Get( )
         return self.StartOf( syFol )

   def Umbriel( self ):
      self.Expect(6)
      self.ModuleIdentifier()
      self.Expect(7)
      self.Block()
      self.ModuleIdentifier()
      self.Expect(8)

   def ModuleIdentifier( self ):
      self.Expect(1)

   def Block( self ):
      while self.StartOf(1):
         self.Declaration()

      if (self.la.kind == 9):
         self.Get( )
         self.StatementSequence()
      self.Expect(10)

   def Declaration( self ):
      if self.la.kind == 11:
         self.Get( )
         while self.la.kind == 1:
            self.ConstantDeclaration()
            self.Expect(7)

      elif self.la.kind == 12:
         self.Get( )
         while self.la.kind == 1:
            self.TypeDeclaration()
            self.Expect(7)

      elif self.la.kind == 13:
         self.Get( )
         while self.la.kind == 1:
            self.VariableDeclaration()
            self.Expect(7)

      elif self.la.kind == 23:
         self.ProcedureDeclaration()
         self.Expect(7)
      else:
         self.SynErr(61)

   def StatementSequence( self ):
      self.Statement()
      while self.la.kind == 7:
         self.Get( )
         self.Statement()


   def ConstantDeclaration( self ):
      self.ConstIdentifier()
      self.Expect(14)
      self.ConstExpression()

   def TypeDeclaration( self ):
      self.TypeIdentifier()
      self.Expect(14)
      self.Type()

   def VariableDeclaration( self ):
      self.IdentList()
      self.Expect(22)
      self.TypeIdentifier()

   def ProcedureDeclaration( self ):
      self.Expect(23)
      self.ProcedureIdentifier()
      if (self.la.kind == 24):
         self.ParameterDeclarations()
      self.Expect(7)
      self.Block()
      self.ProcedureIdentifier()

   def ConstIdentifier( self ):
      self.Expect(1)

   def ConstExpression( self ):
      self.Expression()

   def Expression( self ):
      self.SimpleExpression()
      if (self.StartOf(2)):
         self.Relation()
         self.SimpleExpression()

   def TypeIdentifier( self ):
      self.Expect(1)

   def Type( self ):
      if self.la.kind == 1:
         self.TypeIdentifier()
      elif self.la.kind == 15:
         self.ArrayType()
      elif self.la.kind == 21:
         self.RecordType()
      else:
         self.SynErr(62)

   def ArrayType( self ):
      self.Expect(15)
      self.IndexType()
      while self.la.kind == 16:
         self.Get( )
         self.IndexType()

      self.Expect(17)
      self.Type()

   def RecordType( self ):
      self.Expect(21)
      self.FieldListSequence()
      self.Expect(10)

   def IndexType( self ):
      self.Expect(18)
      self.ConstExpression()
      self.Expect(19)
      self.ConstExpression()
      self.Expect(20)

   def FieldListSequence( self ):
      self.FieldList()
      while self.la.kind == 7:
         self.Get( )
         self.FieldList()


   def FieldList( self ):
      if (self.la.kind == 1):
         self.IdentList()
         self.Expect(22)
         self.Type()

   def IdentList( self ):
      self.VariableIdentifier()
      while self.la.kind == 16:
         self.Get( )
         self.VariableIdentifier()


   def VariableIdentifier( self ):
      self.Expect(1)

   def ProcedureIdentifier( self ):
      self.Expect(1)

   def ParameterDeclarations( self ):
      self.Expect(24)
      if (self.la.kind == 1 or self.la.kind == 13):
         self.FormalParameters()
      self.Expect(25)
      if (self.la.kind == 22):
         self.Get( )
         self.ResultType()

   def FormalParameters( self ):
      self.FormalParameter()
      while self.la.kind == 7:
         self.Get( )
         self.FormalParameter()


   def ResultType( self ):
      self.ScalarTypeIdentifier()

   def ScalarTypeIdentifier( self ):
      self.TypeIdentifier()

   def FormalParameter( self ):
      if self.la.kind == 1:
         self.ValueSpecification()
      elif self.la.kind == 13:
         self.VariableSpecification()
      else:
         self.SynErr(63)

   def ValueSpecification( self ):
      self.IdentList()
      self.Expect(22)
      self.TypeIdentifier()

   def VariableSpecification( self ):
      self.Expect(13)
      self.IdentList()
      self.Expect(22)
      self.TypeIdentifier()

   def Statement( self ):
      if (self.StartOf(3)):
         if self.la.kind == 1:
            self.AssignmentOrCall()
         elif self.la.kind == 27:
            self.IfStatement()
         elif self.la.kind == 31:
            self.CaseStatement()
         elif self.la.kind == 33:
            self.WhileStatement()
         elif self.la.kind == 35:
            self.RepeatStatement()
         elif self.la.kind == 37:
            self.ForStatement()
         elif self.la.kind == 40:
            self.LoopStatement()
         elif self.la.kind == 41:
            self.ExitStatement()
         else:
            self.ReturnStatement()

   def AssignmentOrCall( self ):
      self.VarOrProcIdentifier()
      if self.la.kind == 8 or self.la.kind == 18 or self.la.kind == 26:
         while self.la.kind == 8 or self.la.kind == 18:
            self.Selector()

         self.Get( )
         self.Expression()
      elif self.StartOf(4):
         if (self.la.kind == 24):
            self.Get( )
            if (self.StartOf(5)):
               self.ActualParameters()
            self.Expect(25)
      else:
         self.SynErr(64)

   def IfStatement( self ):
      self.Expect(27)
      self.BooleanExpression()
      self.Expect(28)
      self.StatementSequence()
      while self.la.kind == 29:
         self.Get( )
         self.BooleanExpression()
         self.Expect(28)
         self.StatementSequence()

      if (self.la.kind == 30):
         self.Get( )
         self.StatementSequence()
      self.Expect(10)

   def CaseStatement( self ):
      self.Expect(31)
      self.Expression()
      self.Expect(17)
      self.Case()
      while self.la.kind == 32:
         self.Get( )
         self.Case()

      if (self.la.kind == 30):
         self.Get( )
         self.StatementSequence()
      self.Expect(10)

   def WhileStatement( self ):
      self.Expect(33)
      self.BooleanExpression()
      self.Expect(34)
      self.StatementSequence()
      self.Expect(10)

   def RepeatStatement( self ):
      self.Expect(35)
      self.StatementSequence()
      self.Expect(36)
      self.BooleanExpression()

   def ForStatement( self ):
      self.Expect(37)
      self.VariableIdentifier()
      self.Expect(26)
      self.OrdinalExpression()
      self.Expect(38)
      self.OrdinalExpression()
      if (self.la.kind == 39):
         self.Get( )
         self.ConstExpression()
      self.Expect(34)
      self.StatementSequence()
      self.Expect(10)

   def LoopStatement( self ):
      self.Expect(40)
      self.StatementSequence()
      self.Expect(10)

   def ExitStatement( self ):
      self.Expect(41)

   def ReturnStatement( self ):
      self.Expect(42)
      if (self.StartOf(5)):
         self.Expression()

   def VarOrProcIdentifier( self ):
      self.Expect(1)

   def Selector( self ):
      if self.la.kind == 8:
         self.Get( )
         self.VariableIdentifier()
      elif self.la.kind == 18:
         self.Get( )
         self.IndexList()
         self.Expect(20)
      else:
         self.SynErr(65)

   def ActualParameters( self ):
      self.Expression()
      if (self.la.kind == 22):
         self.FormatSpecifier()
      while self.la.kind == 16:
         self.Get( )
         self.Expression()
         if (self.la.kind == 22):
            self.FormatSpecifier()


   def IndexList( self ):
      self.OrdinalExpression()
      while self.la.kind == 16:
         self.Get( )
         self.OrdinalExpression()


   def OrdinalExpression( self ):
      self.Expression()

   def FormatSpecifier( self ):
      self.Expect(22)
      self.IntegerExpression()
      if (self.la.kind == 22):
         self.Get( )
         self.IntegerExpression()

   def IntegerExpression( self ):
      self.Expression()

   def BooleanExpression( self ):
      self.Expression()

   def Case( self ):
      if (self.StartOf(5)):
         self.CaseLabelList()
         self.Expect(22)
         self.StatementSequence()

   def CaseLabelList( self ):
      self.CaseLabels()
      while self.la.kind == 16:
         self.Get( )
         self.CaseLabels()


   def CaseLabels( self ):
      self.ConstExpression()
      if (self.la.kind == 19):
         self.Get( )
         self.ConstExpression()

   def SimpleExpression( self ):
      if (self.la.kind == 43 or self.la.kind == 44):
         if self.la.kind == 43:
            self.Get( )
         else:
            self.Get( )
      self.Term()
      while self.la.kind == 43 or self.la.kind == 44 or self.la.kind == 53:
         self.AddOperator()
         self.Term()


   def Relation( self ):
      if self.la.kind == 14:
         self.Get( )
      elif self.la.kind == 54:
         self.Get( )
      elif self.la.kind == 55:
         self.Get( )
      elif self.la.kind == 56:
         self.Get( )
      elif self.la.kind == 57:
         self.Get( )
      elif self.la.kind == 58:
         self.Get( )
      elif self.la.kind == 59:
         self.Get( )
      else:
         self.SynErr(66)

   def Term( self ):
      self.Factor()
      while self.StartOf(6):
         self.MulOperator()
         self.Factor()


   def AddOperator( self ):
      if self.la.kind == 43:
         self.Get( )
      elif self.la.kind == 44:
         self.Get( )
      elif self.la.kind == 53:
         self.Get( )
      else:
         self.SynErr(67)

   def Factor( self ):
      if self.StartOf(7):
         self.ConstantLiteral()
      elif self.la.kind == 1:
         self.VarOrFuncOrConstIdentifier()
         if self.StartOf(8):
            while self.la.kind == 8 or self.la.kind == 18:
               self.Selector()

         elif self.la.kind == 24:
            self.Get( )
            if (self.StartOf(5)):
               self.ActualParameters()
            self.Expect(25)
         else:
            self.SynErr(68)
      elif self.la.kind == 45 or self.la.kind == 46:
         self.NotOperator()
         self.Factor()
      elif self.la.kind == 24:
         self.Get( )
         self.Expression()
         self.Expect(25)
      else:
         self.SynErr(69)

   def MulOperator( self ):
      if self.la.kind == 47:
         self.Get( )
      elif self.la.kind == 48:
         self.Get( )
      elif self.la.kind == 49:
         self.Get( )
      elif self.la.kind == 50:
         self.Get( )
      elif self.la.kind == 51 or self.la.kind == 52:
         self.AndOperator()
      else:
         self.SynErr(70)

   def ConstantLiteral( self ):
      if self.la.kind == 3:
         self.Get( )
      elif self.la.kind == 4:
         self.Get( )
      elif self.la.kind == 2:
         self.Get( )
      elif self.la.kind == 5:
         self.Get( )
      else:
         self.SynErr(71)

   def VarOrFuncOrConstIdentifier( self ):
      self.Expect(1)

   def NotOperator( self ):
      if self.la.kind == 45:
         self.Get( )
      elif self.la.kind == 46:
         self.Get( )
      else:
         self.SynErr(72)

   def AndOperator( self ):
      if self.la.kind == 51:
         self.Get( )
      elif self.la.kind == 52:
         self.Get( )
      else:
         self.SynErr(73)



   def Parse( self, scanner ):
      self.scanner = scanner
      self.la = Token( )
      self.la.val = u''
      self.Get( )
      self.Umbriel()
      self.Expect(0)


   set = [
      [T,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x],
      [x,x,x,x, x,x,x,x, x,x,x,T, T,T,x,x, x,x,x,x, x,x,x,T, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x],
      [x,x,x,x, x,x,x,x, x,x,x,x, x,x,T,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,T,T, T,T,T,T, x,x],
      [x,T,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,T, x,x,x,T, x,T,x,T, x,T,x,x, T,T,T,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x],
      [x,x,x,x, x,x,x,T, x,x,T,x, x,x,x,x, x,x,x,x, x,x,x,x, T,x,x,x, x,T,T,x, T,x,x,x, T,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x],
      [x,T,T,T, T,T,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, T,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,T, T,T,T,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x],
      [x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,T, T,T,T,T, T,x,x,x, x,x,x,x, x,x],
      [x,x,T,T, T,T,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x,x,x, x,x],
      [x,x,x,x, x,x,x,T, T,x,T,x, x,x,T,x, T,T,T,T, T,x,T,x, x,T,x,x, T,T,T,x, T,x,T,x, T,x,T,T, x,x,x,T, T,x,x,T, T,T,T,T, T,T,T,T, T,T,T,T, x,x]

      ]

   errorMessages = {

      0 : "EOF expected",
      1 : "identifier expected",
      2 : "char expected",
      3 : "integer expected",
      4 : "real expected",
      5 : "string expected",
      6 : "\"MODULE\" expected",
      7 : "\";\" expected",
      8 : "\".\" expected",
      9 : "\"BEGIN\" expected",
      10 : "\"END\" expected",
      11 : "\"CONST\" expected",
      12 : "\"TYPE\" expected",
      13 : "\"VAR\" expected",
      14 : "\"=\" expected",
      15 : "\"ARRAY\" expected",
      16 : "\",\" expected",
      17 : "\"OF\" expected",
      18 : "\"[\" expected",
      19 : "\"..\" expected",
      20 : "\"]\" expected",
      21 : "\"RECORD\" expected",
      22 : "\":\" expected",
      23 : "\"PROCEDURE\" expected",
      24 : "\"(\" expected",
      25 : "\")\" expected",
      26 : "\":=\" expected",
      27 : "\"IF\" expected",
      28 : "\"THEN\" expected",
      29 : "\"ELSIF\" expected",
      30 : "\"ELSE\" expected",
      31 : "\"CASE\" expected",
      32 : "\"|\" expected",
      33 : "\"WHILE\" expected",
      34 : "\"DO\" expected",
      35 : "\"REPEAT\" expected",
      36 : "\"UNTIL\" expected",
      37 : "\"FOR\" expected",
      38 : "\"TO\" expected",
      39 : "\"BY\" expected",
      40 : "\"LOOP\" expected",
      41 : "\"EXIT\" expected",
      42 : "\"RETURN\" expected",
      43 : "\"+\" expected",
      44 : "\"-\" expected",
      45 : "\"NOT\" expected",
      46 : "\"~\" expected",
      47 : "\"*\" expected",
      48 : "\"/\" expected",
      49 : "\"DIV\" expected",
      50 : "\"MOD\" expected",
      51 : "\"AND\" expected",
      52 : "\"&\" expected",
      53 : "\"OR\" expected",
      54 : "\"#\" expected",
      55 : "\"<>\" expected",
      56 : "\"<\" expected",
      57 : "\"<=\" expected",
      58 : "\">\" expected",
      59 : "\">=\" expected",
      60 : "??? expected",
      61 : "invalid Declaration",
      62 : "invalid Type",
      63 : "invalid FormalParameter",
      64 : "invalid AssignmentOrCall",
      65 : "invalid Selector",
      66 : "invalid Relation",
      67 : "invalid AddOperator",
      68 : "invalid Factor",
      69 : "invalid Factor",
      70 : "invalid MulOperator",
      71 : "invalid ConstantLiteral",
      72 : "invalid NotOperator",
      73 : "invalid AndOperator",
      }
