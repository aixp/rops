# Locale to Windows encoding
# Alexander Shiryaev, 2010

# http://msdn.microsoft.com/ru-ru/goglobal/bb964653(en-us).aspx
# Windows ANSI
windowsAlphaToEncoding = {
# Single Byte Character Set
	'Central Europe': 'cp1250',
	'Cyrillic': 'cp1251',
	'Latin I': 'cp1252',
	'Greek': 'cp1253',
	'Turkish': 'cp1254',
	'Hebrew': 'cp1255',
	'Arabic': 'cp1256',
	'Baltic': 'cp1257',
	'Vietnam': 'cp1258',
	'Thai': 'cp874',
# Double Byte Character Set
	'Japanese Shift-JIS': 'cp932',
	'Simplified Chinese GBK': 'cp936',
	'Korean': 'cp949',
	'Traditional Chinese Big5': 'cp950'
}
# Windows OEM
oemAlphaToEncoding = {
	'US': 'cp437',
	'Arabic': 'cp720',
	'Greek': 'cp737',
	'Baltic': 'cp775',
	'Multilingual Latin I': 'cp850',
	'Latin II': 'cp852',
	'Cyrillic': 'cp855',
	'Turkish': 'cp857',
	'Multilingual Latin I + Euro': 'cp858',
	'Hebrew': 'cp862',
	'Russian': 'cp866',
# the same as in Windows ANSI
	'Thai': windowsAlphaToEncoding['Thai'],
	'Japanese Shift-JIS': windowsAlphaToEncoding['Japanese Shift-JIS'],
	'Simplified Chinese GBK': windowsAlphaToEncoding['Simplified Chinese GBK'],
	'Korean': windowsAlphaToEncoding['Korean'],
	'Traditional Chinese Big5': windowsAlphaToEncoding['Traditional Chinese Big5'],
	'Vietnam': windowsAlphaToEncoding['Vietnam']
}

# iso639 to Windows Alphabet
langToAlpha = {
	'ru': 'Cyrillic',
	'be': 'Cyrillic',
	'bg': 'Cyrillic',
	'kk': 'Cyrillic',
	'el': 'Greek',
	'vi': 'Vietnam',
	'th': 'Thai',
	'ko': 'Korean',
	'ja': 'Japanese Shift-JIS',
	'he': 'Hebrew',

# http://www.science.co.il/language/locale-codes.asp
# http://www.mydigitallife.info/2007/08/12/ansi-code-page-for-windows-system-locale-with-identifier-constants-and-strings/
# language codes in FreeBSD' /usr/share/locale
	'af': 'Latin I', # http://www.science.co.il/language/locale-codes.asp
	'am': None, # Unicode only
	'ca': 'Latin I', # http://www.science.co.il/language/locale-codes.asp
	'cs': 'Central Europe', # http://www.science.co.il/language/locale-codes.asp
	'da': 'Latin I', # http://www.science.co.il/language/locale-codes.asp
	'de': 'Latin I', # http://www.science.co.il/language/locale-codes.asp
	'en': 'Latin I', # http://www.science.co.il/language/locale-codes.asp
	'es': 'Latin I',
	'et': 'Baltic', # http://www.science.co.il/language/locale-codes.asp
	'eu': 'Latin I', # http://www.science.co.il/language/locale-codes.asp
	'fi': 'Latin I', # http://www.science.co.il/language/locale-codes.asp
	'fr': 'Latin I', # http://www.science.co.il/language/locale-codes.asp
	'hi': None, # Unicode only
	'hr': 'Central Europe', # http://www.science.co.il/language/locale-codes.asp
	'hu': 'Central Europe', # http://www.science.co.il/language/locale-codes.asp
	'hy': None, # Unicode only
	'is': 'Latin I', # http://www.science.co.il/language/locale-codes.asp
	'it': 'Latin I', # http://www.science.co.il/language/locale-codes.asp
#	'la': '', # ???
	'lt': 'Baltic', # http://www.science.co.il/language/locale-codes.asp
	'mn': 'Cyrillic',
	'nb': 'Latin I', # http://www.science.co.il/language/locale-codes.asp
	'nl': 'Latin I', # http://www.science.co.il/language/locale-codes.asp
	'nn': 'Latin I', # http://www.science.co.il/language/locale-codes.asp
#	'no': '', # Norwegian; Latin I?
	'pl': 'Central Europe',
	'pt': 'Latin I', # http://www.science.co.il/language/locale-codes.asp
	'ro': 'Central Europe', # http://www.science.co.il/language/locale-codes.asp
	'sk': 'Central Europe', # http://www.science.co.il/language/locale-codes.asp
	'sl': 'Central Europe', # http://www.science.co.il/language/locale-codes.asp
	'sr': 'Cyrillic', # 'Latin I'
	'sv': 'Latin I', # http://www.science.co.il/language/locale-codes.asp
	'tr': 'Turkish',
	'uk': 'Cyrillic',

# http://www.mydigitallife.info/2007/08/12/ansi-code-page-for-windows-system-locale-with-identifier-constants-and-strings/
	'zh_hk': 'Traditional Chinese Big5',
	'zh_cn': 'Simplified Chinese GBK',
	'zh_tw': 'Traditional Chinese Big5',

# http://www.science.co.il/language/locale-codes.asp
	'sq': 'Central Europe', 
	'ar': 'Arabic',
	'az': 'Cyrillic',
	'fo': 'Latin I',
	'fa': 'Arabic',
	'mk': 'Cyrillic',
	'gl': 'Latin I',
	'id': 'Latin I',
	'lv': 'Baltic',
	'ms': 'Latin I',
	'sw': 'Latin I',
	'tt': 'Cyrillic',
	'ur': 'Arabic',
	'uz': 'Cyrillic'
}

def localeToAlpha (localeName):
	localeName = localeName.lower()
	if langToAlpha.has_key(localeName):
		return langToAlpha[localeName]
	elif '_' in localeName:
		return langToAlpha.get(localeName.split('_')[0])

def getByLocale (localeName, oem=False):
	if localeName == None:
		return 'ascii'
	else:
		alpha = localeToAlpha(localeName)
		if alpha != None:
			if oem:
				return oemAlphaToEncoding[alpha]
			else:
				return windowsAlphaToEncoding[alpha]
