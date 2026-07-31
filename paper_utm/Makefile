# Makefile for MUSCAT Paper Compilation

# Main document
MAIN = main
SECTIONS = sections/*.tex
FIGURES = figures/*
TABLES = tables/*
REFS = references/references.bib

# LaTeX compiler
LATEX = pdflatex
BIBTEX = bibtex

# Targets
.PHONY: all clean distclean view

all: $(MAIN).pdf

$(MAIN).pdf: $(MAIN).tex $(SECTIONS) $(REFS)
	@echo "First LaTeX pass..."
	$(LATEX) $(MAIN).tex
	@echo "BibTeX pass..."
	$(BIBTEX) $(MAIN)
	@echo "Second LaTeX pass..."
	$(LATEX) $(MAIN).tex
	@echo "Third LaTeX pass..."
	$(LATEX) $(MAIN).tex
	@echo "✅ PDF generated: $(MAIN).pdf"

quick: $(MAIN).tex
	$(LATEX) $(MAIN).tex
	@echo "✅ Quick compile done (no bibliography)"

view: $(MAIN).pdf
	@if command -v evince > /dev/null; then \
		evince $(MAIN).pdf & \
	elif command -v okular > /dev/null; then \
		okular $(MAIN).pdf & \
	elif command -v xdg-open > /dev/null; then \
		xdg-open $(MAIN).pdf & \
	else \
		echo "Please install a PDF viewer"; \
	fi

clean:
	rm -f $(MAIN).aux $(MAIN).bbl $(MAIN).blg $(MAIN).log $(MAIN).out $(MAIN).toc
	rm -f sections/*.aux
	@echo "✅ Cleaned auxiliary files"

distclean: clean
	rm -f $(MAIN).pdf
	@echo "✅ Cleaned all generated files"

# Count words (approximate)
wordcount:
	@echo "Counting words in LaTeX source..."
	@detex $(MAIN).tex sections/*.tex | wc -w
	@echo "(Note: Approximate count, excludes equations and citations)"

# Check for common LaTeX errors
check:
	@echo "Checking for common issues..."
	@grep -n "\\cite{}" $(MAIN).tex $(SECTIONS) || echo "✓ No empty citations"
	@grep -n "\\ref{}" $(MAIN).tex $(SECTIONS) || echo "✓ No empty references"
	@grep -n "TODO\|FIXME\|XXX" $(MAIN).tex $(SECTIONS) || echo "✓ No TODO markers"
	@echo "✅ Basic checks complete"

# Help
help:
	@echo "MUSCAT Paper Makefile"
	@echo ""
	@echo "Targets:"
	@echo "  all        - Compile paper with bibliography (default)"
	@echo "  quick      - Quick compile without bibliography"
	@echo "  view       - Open PDF in viewer"
	@echo "  clean      - Remove auxiliary files"
	@echo "  distclean  - Remove all generated files including PDF"
	@echo "  wordcount  - Approximate word count"
	@echo "  check      - Check for common issues"
	@echo "  help       - Show this help"

