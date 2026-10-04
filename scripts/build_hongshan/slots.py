# -*- coding: utf-8 -*-
"""新书阅读器的书特定配置（TOC / 章节标题 / 检索标题）。
每个 *_BODY 只含 { ... } 字典体（不含 'const map =' 与分号），由 build_reader 拼装。
本文件为新书《Fighting on the Cultural Front》。
"""

TOC_ORDER = ['abbrev', 'intro', 'ch1', 'ch2', 'ch3', 'ch4', 'ch5', 'ch6',
             'ch7', 'ch8', 'epilogue', 'notes']

TOC_LABEL_BODY = """{
    'abbrev':['Abbreviations','缩写表'],
    'intro':['Introduction','导言'],
    'ch1':['Drawing the Sword','第一章 · 亮出宝剑'],
    'ch2':['Cutting All Ties','第二章 · 一刀两断'],
    'ch3':['Fighting Over the Stranded','第三章 · 争夺滞留者'],
    'ch4':['Building a Cultural Bastion','第四章 · 构筑文化堡垒'],
    'ch5':['Faking the Exchange','第五章 · 虚构的交流'],
    'ch6':['Setting a New Pattern','第六章 · 开创新格局'],
    'ch7':['Forging the Black Blade','第七章 · 铸就黑色利刃'],
    'ch8':['Lowering the Sword','第八章 · 放下宝剑'],
    'epilogue':['Epilogue','结语'],
    'notes':['Notes','注释']
  }"""

TITLE_MAP_BODY = """{
    'abbrev':'缩写表 Abbreviations',
    'intro':'导言 Introduction',
    'ch1':'第一章 · 亮出宝剑 Drawing the Sword',
    'ch2':'第二章 · 一刀两断 Cutting All Ties',
    'ch3':'第三章 · 争夺滞留者 Fighting Over the Stranded',
    'ch4':'第四章 · 构筑文化堡垒 Building a Cultural Bastion',
    'ch5':'第五章 · 虚构的交流 Faking the Exchange',
    'ch6':'第六章 · 开创新格局 Setting a New Pattern',
    'ch7':'第七章 · 铸就黑色利刃 Forging the Black Blade',
    'ch8':'第八章 · 放下宝剑 Lowering the Sword',
    'epilogue':'结语 · Epilogue: Beyond Rattling',
    'notes':'注释 Notes'
  }"""

SECTITLE_BODY = """{
    'abbrev':'缩写表 · Abbreviations','intro':'导言 · Introduction',
    'ch1':'第一章 · 亮出宝剑','ch2':'第二章 · 一刀两断','ch3':'第三章 · 争夺滞留者',
    'ch4':'第四章 · 构筑文化堡垒','ch5':'第五章 · 虚构的交流','ch6':'第六章 · 开创新格局',
    'ch7':'第七章 · 铸就黑色利刃','ch8':'第八章 · 放下宝剑','epilogue':'结语 · Epilogue',
    'notes':'注释 · Notes'
  }"""