# Arabic fonts for checking

Only needed for the *checking* loop, not for the converter itself. The .docx we
produce names the original font; on Windows with Word those fonts already
exist.

On Linux, without substitutes every Arabic face falls back to Noto Sans Arabic,
which is wider than the fonts these documents ask for. Text then overflows when
LibreOffice renders our file, and the overflow is blamed on the converter.
Installing these moved one file from 70% to 80% on the right-page score and
fixed its page count exactly.

    mkdir -p ~/.local/share/fonts/arabic
    cd ~/.local/share/fonts/arabic
    B=https://raw.githubusercontent.com/google/fonts/main/ofl
    curl -fsSLO $B/amiri/Amiri-Regular.ttf
    curl -fsSLO $B/amiri/Amiri-Bold.ttf
    curl -fsSLO $B/scheherazadenew/ScheherazadeNew-Regular.ttf
    curl -fsSLO $B/scheherazadenew/ScheherazadeNew-Bold.ttf
    curl -fsSLO $B/lateef/Lateef-Regular.ttf
    curl -fsSL -o Cairo.ttf "$B/cairo/Cairo%5Bslnt%2Cwght%5D.ttf"
    curl -fsSL -o MarkaziText.ttf "$B/markazitext/MarkaziText%5Bwght%5D.ttf"
    fc-cache -f ~/.local/share/fonts

Then map the requested faces onto them - copy
`docs/60-arabic-substitutes.conf` to `~/.config/fontconfig/conf.d/`.

Check it worked:

    fc-match "Simplified Arabic"    # should NOT say Noto
