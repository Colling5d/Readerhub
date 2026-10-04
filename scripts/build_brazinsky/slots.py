# -*- coding: utf-8 -*-
"""本书阅读器的书特定配置（TOC / 章节标题 / 检索标题）。
Gregg A. Brazinsky, Winning the Third World。
"""

TOC_ORDER = ['intro', 'ch1', 'ch2', 'ch3', 'ch4', 'ch5', 'ch6', 'ch7',
             'ch8', 'ch9', 'ch10', 'conclusion', 'notes']

TOC_LABEL_BODY = """{
    'intro':['Introduction','导言'],
    'ch1':['The Emergence of a Rivalry','第一章 · 竞争关系的产生'],
    'ch2':['The Burdens of Status','第二章 · 地位的负担'],
    'ch3':['From Geneva to Bandung','第三章 · 从日内瓦到万隆'],
    'ch4':['Advancing the Peace Offensive','第四章 · 推进和平攻势'],
    'ch5':['The Cultural Competition','第五章 · 文化竞争'],
    'ch6':["China's Radicalization and the American Response",'第六章 · 中国的激进与美国的回应'],
    'ch7':['The Diplomatic Campaign','第七章 · 外交运动'],
    'ch8':['Insurgency and Counterinsurgency','第八章 · 叛乱与反叛乱'],
    'ch9':['The Economic Competition','第九章 · 经济竞争'],
    'ch10':['Competition and Cooperation','第十章 · 竞争与合作'],
    'conclusion':['Conclusion','结语'],
    'notes':['Notes','注释']
  }"""

TITLE_MAP_BODY = """{
    'intro':'导言 · Introduction: Winning the Third World',
    'ch1':'第一章 · 竞争关系的产生 The Emergence of a Rivalry',
    'ch2':'第二章 · 地位的负担 The Burdens of Status',
    'ch3':'第三章 · 从日内瓦到万隆 From Geneva to Bandung',
    'ch4':'第四章 · 推进和平攻势 Advancing the Peace Offensive',
    'ch5':'第五章 · 文化竞争 The Cultural Competition',
    'ch6':'第六章 · 中国的激进与美国的回应 China\\'s Radicalization and the American Response',
    'ch7':'第七章 · 外交运动 The Diplomatic Campaign',
    'ch8':'第八章 · 叛乱与反叛乱 Insurgency and Counterinsurgency',
    'ch9':'第九章 · 经济竞争 The Economic Competition',
    'ch10':'第十章 · 竞争与合作 Competition and Cooperation',
    'conclusion':'结语 · Conclusion: China, Status, and the Third World',
    'notes':'注释 Notes'
  }"""

SECTITLE_BODY = """{
    'intro':'导言 · Introduction','ch1':'第一章 · 竞争关系的产生','ch2':'第二章 · 地位的负担',
    'ch3':'第三章 · 从日内瓦到万隆','ch4':'第四章 · 推进和平攻势','ch5':'第五章 · 文化竞争',
    'ch6':'第六章 · 中国的激进与美国的回应','ch7':'第七章 · 外交运动','ch8':'第八章 · 叛乱与反叛乱',
    'ch9':'第九章 · 经济竞争','ch10':'第十章 · 竞争与合作',
    'conclusion':'结语 · Conclusion','notes':'注释 · Notes'
  }"""