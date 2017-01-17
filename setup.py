from distutils.core import setup

setup(
	name = "ROPS",
	packages = ["rops",],
	version = "0.8",
	platforms = ['POSIX', 'Windows'],
	description = "Simple text editor",
	author = "Alexander Shiryaev",
	author_email = "shiryaev.a.v@gmail.com",
	url = "http://hep.msu.dubna.ru/~shiryaev/rops/",
	download_url = "http://hep.msu.dubna.ru/~shiryaev/files/rops/rops-0.8.tar.gz",
	keywords = ["oberon", "component pascal", "zonnon"],
	package_data = { 'rops': ['ide-gtk2.glade', 'ide-gtk3.glade', 'translations/*', 'cocodrivers/*.*', 'cocodrivers/Umbriel/*', 'cocodrivers/Oberon0/*'] },
)
