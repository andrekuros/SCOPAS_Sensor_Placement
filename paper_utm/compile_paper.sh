#!/bin/bash
# Script para compilar o paper MUSCAT

echo "=========================================="
echo "COMPILAÇÃO DO PAPER MUSCAT"
echo "=========================================="
echo ""

# Verificar se pdflatex está disponível
if ! command -v pdflatex &> /dev/null; then
    echo "❌ ERRO: pdflatex não encontrado!"
    echo "   Instale: sudo apt-get install texlive-latex-base"
    exit 1
fi

# Verificar se IEEEtran.cls está disponível
if ! kpsewhich IEEEtran.cls &> /dev/null; then
    echo "⚠️  AVISO: IEEEtran.cls não encontrado!"
    echo ""
    echo "Para instalar IEEEtran:"
    echo "  Opção 1 (tlmgr): sudo tlmgr install ieeetran"
    echo "  Opção 2 (apt):   sudo apt-get install texlive-publishers"
    echo ""
    echo "Continuando compilação (pode falhar)..."
    echo ""
fi

# Verificar se bibtex está disponível
if ! command -v bibtex &> /dev/null; then
    echo "⚠️  AVISO: bibtex não encontrado!"
    echo "   Instale: sudo apt-get install texlive-bibtex-extra"
    echo ""
fi

# Diretório do paper
PAPER_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PAPER_DIR"

echo "📄 Compilando main.tex..."
echo ""

# Primeira passagem pdflatex
echo "1/4 - Primeira passagem pdflatex..."
pdflatex -interaction=nonstopmode -output-directory=. main.tex > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Erro na primeira passagem pdflatex"
    echo "   Verifique main.log para detalhes"
    exit 1
fi

# Bibtex
if command -v bibtex &> /dev/null; then
    echo "2/4 - Executando bibtex..."
    bibtex main > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "⚠️  Aviso: bibtex teve problemas (pode ser normal)"
    fi
else
    echo "2/4 - Pulando bibtex (não disponível)"
fi

# Segunda passagem pdflatex
echo "3/4 - Segunda passagem pdflatex..."
pdflatex -interaction=nonstopmode -output-directory=. main.tex > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Erro na segunda passagem pdflatex"
    exit 1
fi

# Terceira passagem pdflatex (para referências cruzadas)
echo "4/4 - Terceira passagem pdflatex..."
pdflatex -interaction=nonstopmode -output-directory=. main.tex > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Erro na terceira passagem pdflatex"
    exit 1
fi

# Verificar se PDF foi gerado
if [ -f "main.pdf" ]; then
    PDF_SIZE=$(du -h main.pdf | cut -f1)
    echo ""
    echo "✅ COMPILAÇÃO CONCLUÍDA!"
    echo "   PDF gerado: main.pdf ($PDF_SIZE)"
    echo ""
    echo "📋 Próximos passos:"
    echo "   1. Abrir main.pdf e revisar visualmente"
    echo "   2. Verificar formatação IEEE"
    echo "   3. Confirmar todas as figuras aparecem corretamente"
    echo "   4. Verificar referências cruzadas"
else
    echo ""
    echo "❌ ERRO: PDF não foi gerado!"
    echo "   Verifique main.log para detalhes"
    exit 1
fi

