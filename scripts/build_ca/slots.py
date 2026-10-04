# -*- coding: utf-8 -*-
"""新书阅读器的书特定配置（TOC / 章节标题 / 检索标题）。
每个 *_BODY 只含 { ... } 字典体（不含 'const map =' 与分号），由 build_reader 拼装。
"""

# 章节顺序
TOC_ORDER = ['fwd', 'spell', 'intro', 'ch1', 'ch2', 'ch3', 'ch4', 'ch5', 'ch6',
             'concl', 'notes', 'glossary', 'biblio', 'ack', 'index']

# tocLabel 用的字典体
TOC_LABEL_BODY = """{
    'fwd':['Foreword','前言'],
    'spell':['A Note on the Spelling of Chinese Names','中文姓名拼写说明'],
    'intro':['Introduction','导言'],
    'ch1':['Anson Burlingame','第一章 · 安森·蒲安臣'],
    'ch2':['The Chinese Education Mission','第二章 · 幼童留美教育'],
    'ch3':['Ge Kunhua','第三章 · 戈鲲化'],
    'ch4':['Frank Goodnow','第四章 · 弗兰克·古德诺'],
    'ch5':['John Dewey','第五章 · 约翰·杜威'],
    'ch6':['Shared Diplomatic Journey through Sports','第六章 · 体育外交的共同旅程'],
    'concl':['Conclusion','结语'],
    'notes':['Notes','注释'],
    'glossary':['Selected Glossary','术语表'],
    'biblio':['Selected Bibliography','参考书目'],
    'ack':['Acknowledgments','致谢'],
    'index':['Index','索引']
  }"""

# goTo 里的 titleMap 字典体（章节大标题）
TITLE_MAP_BODY = """{
    'fwd':'前言 Foreword',
    'spell':'中文姓名拼写说明 · A Note on the Spelling of Chinese Names',
    'intro':'导言 Introduction',
    'ch1':'第一章 · 安森·蒲安臣：作为美国文明使者的对华代表',
    'ch2':'第二章 · 幼童留美教育：中国走向世界的尝试',
    'ch3':'第三章 · 戈鲲化：来自东方的汉学使者',
    'ch4':'第四章 · 弗兰克·古德诺：在华美国顾问',
    'ch5':'第五章 · 约翰·杜威：美国人实用主义的哲学家大使',
    'ch6':'第六章 · 体育外交：中美共同的外交之旅',
    'concl':'结语 · Conclusion',
    'notes':'注释 Notes',
    'glossary':'术语表 Selected Glossary',
    'biblio':'参考书目 Selected Bibliography',
    'ack':'致谢 Acknowledgments',
    'index':'索引 Index'
  }"""

# 检索用的 secTitle 字典体
SECTITLE_BODY = """{
    'fwd':'前言 · Foreword','spell':'中文姓名拼写说明 · Note on Spelling',
    'intro':'导言 · Introduction','ch1':'第一章 · 蒲安臣','ch2':'第二章 · 幼童留美教育',
    'ch3':'第三章 · 戈鲲化','ch4':'第四章 · 古德诺','ch5':'第五章 · 杜威',
    'ch6':'第六章 · 体育外交','concl':'结语 · Conclusion','notes':'注释 · Notes',
    'glossary':'术语表 · Glossary','biblio':'参考书目 · Bibliography',
    'ack':'致谢 · Acknowledgments','index':'索引 · Index'
  }"""