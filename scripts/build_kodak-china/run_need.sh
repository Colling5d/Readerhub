#!/bin/zsh
export ECNU_API_KEY="sk-e1d6953fb6c348d193d8dd4a03c6edc7"
export ECNU_API_BASE="https://chat.ecnu.edu.cn/open/api/v1/chat/completions"
export ECNU_API_MODEL="ecnu-max"
export ECNU_WORKERS="6"
export ECNU_DELAY="1.5"
cd /Users/zhulv/ReaderHub/scripts/build_kodak-china
python3 translate_need.py
