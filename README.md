# Simple text editor with syntax checking

## Install

```shell
sudo pacman -S gtksourceview3
pip install .
```

```shell
mkdir -p ~/.local/share/gtksourceview-3.0/language-specs
cp oberon.lang zonnon.lang ~/.local/share/gtksourceview-3.0/language-specs/
```

```shell
mkdir -p ~/.local/share/gtksourceview-3.0/styles
cp strict.xml ~/.local/share/gtksourceview-3.0/styles/
```

## Run

```shell
rops
```
