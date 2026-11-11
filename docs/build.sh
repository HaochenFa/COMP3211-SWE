#!/bin/sh
# Typeset the course documents as PDFs. Sources are grouped under docs/ in
# assignment order; every PDF is written to the source root:
#
#   SRS.pdf  DESIGN_REPORT.pdf  USER_MANUAL.pdf  DEVELOPER_MANUAL.pdf
#   REQUIREMENTS.pdf  COVERAGE_REPORT.pdf
#
# The brief asks for the requirements coverage report and the line-coverage
# report in the root folder of the source code, so their PDFs sit next to pim.py.
#
# The Markdown files stay the only source of the text. The page design lives
# in docs/_typeset/: template.tex (title page, contents, running headers,
# tables, requirement blocks), filter.lua (turns the Markdown into those LaTeX
# structures), and mermaid.json (diagram theme). Diagram sources are in
# docs/_diagrams/. Title-page details (group number, members) come from
# docs/group.yaml.
#
# Documentation tooling only: it is not part of the PIM implementation, so the
# standard-library-only rule does not apply. Needs pandoc 3, XeLaTeX (MacTeX),
# mermaid-cli (mmdc), and Google Chrome for mmdc (override with
# PUPPETEER_EXECUTABLE_PATH). Usage from the repository root:
#
#     sh docs/build.sh            # every document
#     sh docs/build.sh SRS DESIGN # only these (named by their source file)

set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
REQUIREMENTS="$ROOT/docs/01-requirements"
DESIGN="$ROOT/docs/02-design"
IMPLEMENTATION="$ROOT/docs/03-implementation"
TESTS="$ROOT/docs/04-unit-tests"
GROUP="$ROOT/docs/group.yaml"
TYPESET="$ROOT/docs/_typeset"
DIAGRAMS="$ROOT/docs/_diagrams"

for tool in pandoc mmdc python3; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "build: $tool not found" >&2
        exit 1
    fi
done
if command -v xelatex >/dev/null 2>&1; then
    TEX_ENGINE=xelatex
elif command -v tectonic >/dev/null 2>&1; then
    TEX_ENGINE=tectonic
else
    echo "build: install XeLaTeX (MacTeX) or Tectonic" >&2
    exit 1
fi

BUILD=$(mktemp -d "${TMPDIR:-/tmp}/pim-docs.XXXXXX")
trap 'rm -rf "$BUILD"' EXIT
mkdir -p "$BUILD/diagrams"

# ------------------------------------------------------------------ diagrams
# mmdc drives a headless browser; reuse the installed Chrome instead of a
# puppeteer download. The diagrams use Source Sans 3 (shipped with TeX Live)
# so they match the document headings; the font is embedded in the CSS.
CHROME=${PUPPETEER_EXECUTABLE_PATH:-"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"}
printf '{"executablePath": "%s", "args": ["--no-sandbox"]}\n' "$CHROME" > "$BUILD/puppeteer.json"

if command -v kpsewhich >/dev/null 2>&1 && kpsewhich SourceSans3-Regular.otf >/dev/null 2>&1; then
    SANS=$(dirname "$(kpsewhich SourceSans3-Regular.otf)")
    {
        for face in Regular:400 Semibold:600 Bold:700; do
            file=${face%%:*}
            weight=${face##*:}
            printf '@font-face{font-family:"Source Sans 3";font-weight:%s;src:url(data:font/otf;base64,%s) format("opentype");}\n' \
                "$weight" "$(base64 < "$SANS/SourceSans3-$file.otf" | tr -d '\n')"
        done
        cat "$TYPESET/mermaid.css"
    } > "$BUILD/diagram-fonts.css"
else
    if ! command -v fc-match >/dev/null 2>&1; then
        echo "build: install Source Sans 3 and fontconfig for Tectonic" >&2
        exit 1
    fi
    SANS_FONT=$(fc-match -f '%{file}' "Source Sans 3")
    if [ ! -f "$SANS_FONT" ]; then
        echo "build: Source Sans 3 font not found" >&2
        exit 1
    fi
    {
        printf '@font-face{font-family:"Source Sans 3";font-weight:400 700;src:url(data:font/ttf;base64,%s) format("truetype");}\n' \
            "$(base64 < "$SANS_FONT" | tr -d '\n')"
        cat "$TYPESET/mermaid.css"
    } > "$BUILD/diagram-fonts.css"
fi

for src in "$DIAGRAMS"/*.mmd; do
    name=$(basename "$src" .mmd)
    echo "build: diagram $name"
    mmdc -q -p "$BUILD/puppeteer.json" -c "$TYPESET/mermaid.json" -C "$BUILD/diagram-fonts.css" \
        -i "$src" -o "$BUILD/diagrams/$name.pdf" -b white
done

# ------------------------------------------------------------------ documents
# Wrap the plain-text coverage report so it renders as a document.
python3 "$TYPESET/coverage_doc.py" "$TESTS/coverage.txt" "$(date '+%-d %B %Y')" > "$BUILD/coverage.md"

ONLY="$*"

render() {
    # $1 = Markdown source, $2 = output PDF path
    name=$(basename "$1" .md)
    # Optional arguments name the documents to build, e.g. "SRS DESIGN".
    if [ -n "$ONLY" ] && ! printf ' %s ' "$ONLY" | grep -q " $name "; then
        return 0
    fi
    echo "build: $(basename "$2")"
    PIM_BUILD_DIR="$BUILD" pandoc "$1" \
        --from markdown \
        --to latex \
        --template="$TYPESET/template.tex" \
        --lua-filter="$TYPESET/filter.lua" \
        --metadata-file="$GROUP" \
        --resource-path="$BUILD:$REQUIREMENTS:$DESIGN:$IMPLEMENTATION:$TESTS:$ROOT" \
        -o "$BUILD/$name.tex"
    # Three passes: contents, figure list, and the "Page n of N" footer.
    if [ "$TEX_ENGINE" = xelatex ]; then
        for pass in 1 2 3; do
            if ! (cd "$BUILD" && xelatex -interaction=nonstopmode -halt-on-error "$name.tex" > "$name.out" 2>&1); then
                grep -E '^!' -A4 "$BUILD/$name.log" >&2 || tail -20 "$BUILD/$name.out" >&2
                echo "build: xelatex failed on $name" >&2
                exit 1
            fi
        done
    elif ! (cd "$BUILD" && tectonic --keep-logs --keep-intermediates --reruns 3 --outdir "$BUILD" "$name.tex" > "$name.out" 2>&1); then
        tail -20 "$BUILD/$name.out" >&2
        echo "build: tectonic failed on $name" >&2
        exit 1
    fi
    if grep -q 'Missing character' "$BUILD/$name.log"; then
        echo "build: warning: $name uses characters its fonts lack:" >&2
        grep 'Missing character' "$BUILD/$name.log" | sort -u >&2
    fi
    cp "$BUILD/$name.pdf" "$2"
}

render "$REQUIREMENTS/SRS.md" "$ROOT/SRS.pdf"
render "$DESIGN/DESIGN.md" "$ROOT/DESIGN_REPORT.pdf"
render "$IMPLEMENTATION/USER.md" "$ROOT/USER_MANUAL.pdf"
render "$IMPLEMENTATION/DEVELOPER.md" "$ROOT/DEVELOPER_MANUAL.pdf"
render "$IMPLEMENTATION/REQUIREMENTS.md" "$ROOT/REQUIREMENTS.pdf"
render "$BUILD/coverage.md" "$ROOT/COVERAGE_REPORT.pdf"

echo "build: done"
