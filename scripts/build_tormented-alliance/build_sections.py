#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The Tormented Alliance: en_data.json 已由 extract.py 直接产出，此脚本仅校验。"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, 'en_data.json'), encoding='utf-8'))
print('sections', len(d), 'paras', sum(len(s['paras']) for s in d))
