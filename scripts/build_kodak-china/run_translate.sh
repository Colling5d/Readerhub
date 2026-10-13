#!/bin/bash
# 华师大 ECNU 翻译：单进程守护式运行，日志写 translate.log
cd "$(dirname "$0")"
export ECNU_API_KEY="sk-e1d6953fb6c348d193d8dd4a03c6edc7"
export ECNU_API_BASE="https://chat.ecnu.edu.cn/open/api/v1/chat/completions"
export ECNU_API_MODEL="ecnu-max"
export ECNU_WORKERS="6"
export ECNU_DELAY="1.5"
exec python3 translate.py >> translate.log 2>&1
