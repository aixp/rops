Простой текстовый (р)едактор
в первую очередь для языков программирования семейства (О)берон
с (п)роверкой (с)интаксиса

This is a simple text editor
first of all for Oberon-family programming languages
with syntax checking

ROPS is transliterated abbreviation

Requirements:

	Ubuntu:

		GTK2-version:
			python-gtksourceview2

		GTK3-version:
			gir1.2-gtksource-3.0
			python-gi-cairo
			python-chardet

Install:

	GTK2-version:
		cat > ~/bin/rops <<DATA
		#!/bin/sh
		exec python2.7 `readlink -f rops/ide_gtk2.py` "${@}"
		DATA
		chmod +x ~/bin/rops

		mkdir -p ~/.local/share/gtksourceview-2.0/language-specs
		cp oberon.lang zonnon.lang ~/.local/share/gtksourceview-2.0/language-specs/

		mkdir -p ~/.local/share/gtksourceview-2.0/styles
		cp strict.xml ~/.local/share/gtksourceview-2.0/styles/

	GTK3-version:
		cat > ~/bin/rops <<DATA
		#!/bin/sh
		exec python2.7 `readlink -f rops/ide_gtk3.py` "${@}"
		DATA
		chmod +x ~/bin/rops

		ln -s `readlink -f rops/ide_gtk3.py` ~/bin/rops

		mkdir -p ~/.local/share/gtksourceview-3.0/language-specs
		cp oberon.lang zonnon.lang ~/.local/share/gtksourceview-3.0/language-specs/

		mkdir -p ~/.local/share/gtksourceview-3.0/styles
		cp strict.xml ~/.local/share/gtksourceview-3.0/styles/

Alexander Shiryaev, 2010-2017
