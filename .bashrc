
export TERM=xterm-256color

# Load alias & setting sistem kalau mau
if [ -f /etc/bash.bashrc ]; then
    . /etc/bash.bashrc
fi
# Auto load Xresources jika X aktif
if [[ -n "$DISPLAY" ]] && command -v xrdb >/dev/null 2>&1; then
    xrdb -merge /home/leakos/.Xresources
fi

#if [[ -z $DISPLAY && $(tty) = /dev/tty1 ]]; then
     #startx >/dev/null 2>&1
#fi

# Pastikan PROMPT_COMMAND tidak mengganggu
unset PROMPT_COMMAND 2>/dev/null

# Prompt Parrot/Kali style untuk root (hanya di sini!)
export PS1='\[\033[1;31m\]┌──(\[\033[1;91m\]\u㉿\h\[\033[1;31m\])-[\[\033[1;96m\]\w\[\033[1;31m\]]\n└─\[\033[1;91m\]#\[\033[0m\] '
