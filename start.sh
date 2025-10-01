echo -ne "\e[?1049h"
clear

python3 quik.py $@

echo -ne "\e[?1049l"
