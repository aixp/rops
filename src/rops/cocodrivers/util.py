# Alexander Shiryaev, 2011, 2024

# Driver.Process result ->profiles compile result
def toCompileResult (x):
	msg = []
	errs = []
	warns = []
	i = 0
	for line, col, s in x:
		errs.append( (i, (line - 1, col - 1)) )
		msg.append(s)
		i = i + 1
	return ( '\n'.join(msg), errs, warns )
