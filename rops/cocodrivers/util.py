# Alexander Shiryaev, 2011

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
	return ( u'\n'.join(msg), errs, warns )

if __name__ == '__main__':
	main()
