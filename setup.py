from distutils.core import setup

setup(
	name = "ROPS",
	packages = ["rops",],
	version = "0.6",
	platforms = ['POSIX', 'Windows'],
	description = "Simple text editor",
	author = "Alexander Shiryaev",
	author_email = "shiryaev.a.v@gmail.com",
	url = "http://hep.msu.dubna.ru/~shiryaev/rops/",
	download_url = "http://hep.msu.dubna.ru/~shiryaev/files/rops/rops-0.6.tar.gz",
	keywords = ["oberon", "component pascal", "zonnon"],
	package_data = { 'rops': ['ide.glade', 'translations/*', 'cocodrivers/*.*', 'cocodrivers/Umbriel/*', 'cocodrivers/Oberon0/*'] },
)
