# Alexander Shiryaev, 2011

from . import Scanner
from . import Parser



def Process (s):
	scanner = Scanner.Scanner(s)
	parser = Parser.Parser()

	Parser.Errors.Init('', '', True, parser.getParsingPos, parser.errorMessages)
	Parser.Errors.errors = []
	Parser.Errors.count = 0

	parser.Parse(scanner)
	Parser.Errors.Summarize(scanner.buffer)

	return tuple( [ (e.line, e.col, e.str) for e in Parser.Errors.errors ] )

