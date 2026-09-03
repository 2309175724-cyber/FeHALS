.DEFAULT_GOAL := main

main: Manuscript.tex
	latexmk -xelatex -outdir=build $<
	cp build/$(basename $<).pdf ../DESCRIPTION.pdf

DRAWIO_SRC := $(wildcard figs/src/*.drawio)
DRAWIO_PDF := $(patsubst figs/src/%.drawio, figs/%.pdf, $(DRAWIO_SRC))

drawio: $(DRAWIO_PDF)

$(DRAWIO_PDF): figs/%.pdf: figs/src/%.drawio
	drawio -x -f pdf -e --crop -o $@ $<