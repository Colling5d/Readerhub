#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全文翻译 + 句子对齐（综合 prompt）。
读取 en_data.json → 每个 text/note 段落做 清洁英文+中译+切句+对齐；h 段做纯翻译。
产出 work/translated.json（按 'secid/i' 键，断点续跑）。
"""
import json, os, re, time, threading, urllib.request, math, sys

BASE = os.environ.get('ECNU_API_BASE', 'https://chat.ecnu.edu.cn/open/api/v1/chat/completions')
KEY = os.environ.get('ECNU_API_KEY', 'sk-e1d6953fb6c348d193d8dd4a03c6edc7')
MODEL = os.environ.get('ECNU_API_MODEL', 'ecnu-max')
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, 'work')
os.makedirs(WORK, exist_ok=True)
OUT = os.path.join(WORK, 'translated.json')
EN_DATA = os.path.join(HERE, 'en_data.json')

NWORKERS = int(os.environ.get('ECNU_WORKERS', 1))
BATCH = int(os.environ.get('ECNU_BATCH', 6))
BATCH_CHARS = int(os.environ.get('ECNU_CHARS', 3800))
MAX_TOK = 16000
CALL_DELAY = float(os.environ.get('ECNU_DELAY', 3.0))   # 每次调用间的线程内固定间隔，减轻 429

def norm(s):
    return ' '.join(s.split())

def call_api(prompt, max_tokens=MAX_TOK, retries=6):
    payload = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                          "temperature": 0, "max_tokens": max_tokens}).encode()
    last = None
    for a in range(retries):
        try:
            req = urllib.request.Request(BASE, data=payload, headers={"Content-Type": "application/json",
                                                                      "Authorization": "Bearer " + KEY})
            resp = json.loads(urllib.request.urlopen(req, timeout=360).read())
            content = resp['choices'][0]['message']['content'].strip()
            if content.startswith('```'):
                content = content.split('\n', 1)[1].rsplit('```', 1)[0].strip()
            return content
        except Exception as e:
            last = e
            backoff = 4 + a * 8 if '429' in str(e) else 3 + a * 4
            print(f"    [retry {a+1}] {str(e)[:80]} (backoff {backoff}s)", flush=True)
            time.sleep(backoff)
    raise last

GLOSSARY = (
    "本书为中美关系史专著（Zach Fredman, The Tormented Alliance: American Servicemen and the "
    "Occupation of China, 1941–1949, UNC Press, 2022）。术语统一如下：\n"
    "Guomindang (GMD)=国民党；Nationalist Party=国民党；Republic of China (ROC)=中华民国；"
    "Chiang Kai-shek=蒋介石；Mao Zedong=毛泽东；Zhou Enlai=周恩来；Stilwell=史迪威；"
    "Chennault=陈纳德；Wedemeyer=魏德迈；Huang Renlin=黄仁霖；Dai Li=戴笠；Soong Mei-ling=宋美龄；"
    "T. V. Soong=宋子文；Marshall=马歇尔；Hurley=赫尔利；Wedemeyer=魏德迈；Boatner=包瑞德/鲍特纳；"
    "American Volunteer Group (AVG)=美国志愿航空队；Flying Tigers=飞虎队；"
    "War Area Service Corps (WASC)=战地服务团；hostel program=招待所计划/励志社招待所；"
    "interpreting officer=翻译官；interpreter program=翻译官计划；"
    "China Theater=中国战区；CBI=中印缅战区；SACO=中美特种技术合作所；"
    "Operation Ichigo=豫湘桂战役（一号作战）；Burma Road=滇缅公路；the Hump=驼峰航线；"
    "Kunming=昆明；Chongqing=重庆；Qingdao=青岛；Shanghai=上海；Beijing=北京；Nanjing=南京；"
    "jeep girl=吉普女郎；GI=美国大兵；enlisted men=士兵；servicemen=军人；"
    "extraterritoriality=治外法权；status of forces agreement (SOFA)=驻军地位协定；"
    "occupation=占领；military occupation=军事占领；unequal treaties=不平等条约；"
    "Anti-Brutality Movement=抗暴运动；Resist America and Aid Korea=抗美援朝；"
    "Lend-Lease=租借法案；mutual aid=互助；black market=黑市；night soil=粪肥；"
    "Fourteenth Air Force=第十四航空队；China-Burma-India=中印缅；"
    "Dixie Mission=迪克西使团；Office of War Information=战时新闻局；"
)

COMBINED = (
    "你是中英对照的学术专著翻译与句子对齐专家。下面若干段英文来自一本学术专著的 PDF 文字层"
    "（可能有断字、断行、引号/上标脚注号被拆开等问题，如 'inter- preters'→'interpreters'、"
    "'⑪' 或 '11' 为上标脚注号）。\n"
    + GLOSSARY +
    "针对每一段做四件事：\n"
    "1) 复原出**干净、通顺、拼写正确**的英文 en（修正断字/缺字/并字，恢复正确标点与上标脚注号，"
    "不改变原意、不增删实质内容；若原文本就是完整正确的，原样保留；方括号内是作者的插入说明，"
    "如 [sic]、[and]、[GMD]，应保留在正确位置）；\n"
    "2) 把 en 准确翻译成通顺、符合中文社科学术专著（商务印书馆式）风格的中文 zh；"
    "人名、地名、机构名用通行中文译名，首次出现可加原文；中文夹注保持学术规范；\n"
    "3) 把 en 切分为句子列表 en_sents，zh 切分为 zh_sents；\n"
    "4) 给出中英句子对齐 align：[[英句下标,中句下标],...]，允许一对多/多对一。\n"
    "硬性要求：\n"
    "- 每个对象的 key 必须**原样**保留我给出的标识；\n"
    "- en_sents 顺序首尾拼接必须**逐字符等于 en**；zh_sents 逐字符拼接等于 zh。为满足这点：\n"
    "   * 先完整写下 en，再从 en 里切句，每句必须能从 en 中连续取原词（含标点）；\n"
    "   * 先完整写下 zh，再从 zh 里切句；\n"
    "   * 切勿在 en 与 en_sents 之间、zh 与 zh_sents 之间改动任何词、空格或标点；\n"
    "- 中文句号用“。”；绝不截断；脚注号、页码按原样放进 en 与对应句；\n"
    "- 诗体（分行诗）按诗行切句，译文尽量保留分行。\n"
    "自检：en_sents 用空串 join 后必须与 en 完全相同，否则修正后再输出。\n"
    "只输出一个 JSON 数组（不要 Markdown 代码块、不要任何解释），按给出顺序每段一个对象：\n"
    "{\"key\":\"标识\",\"en\":\"...\",\"zh\":\"...\",\"en_sents\":[...],\"zh_sents\":[...],\"align\":[[0,0],...]}\n\n"
    "段落如下：\n"
)

def build_combined(batch):
    ps = ""
    for key, text in batch:
        ps += f"\n--- {key} ---\n{text}\n"
    # 按批次内首个样本检测语言：含西里尔字母 → 俄汉对照 prompt
    src = batch[0][1] if batch else ""
    prompt = COMBINED_RU if re.search(r'[\u0400-\u04FF]', src) else COMBINED
    return prompt + ps

COMBINED_RU = (
    "你是俄汉对照的档案文献翻译与句子对齐专家。下面给出若干段俄文（来自一本档案汇编的OCR，"
    "可能存在OCR断词/并字/标点错误，如 'кита йской'→'китайской'、'СССРМ'→'СССР М'、"
    "连字符断行 'по-\nмощью'→'помощью'；引用的人名/地名/机构名务必按上下文补全拼写）。\n"
    "针对每一段做四件事：\n"
    "1) 复原出**干净、通顺、拼写正确**的俄文 en 字段（字段名沿用 en，实为俄文原文；修正OCR断词/缺字/并字，"
    "恢复正确标点，不改变原意、不增删实质内容；若原文本就是完整正确的，原样保留；斜体印刷标注如 "
    "«Совершенно секретно» 等密级/转发标记原样保留）；\n"
    "2) 把 en 准确翻译成通顺、符合档案文献汇编风格的中文 zh（人名地名人名用通行中文译名，如 列宁、斯大林、"
    "蒋介石、宋子文、鲍罗廷、卡拉汉、李维诺夫、莫洛托夫；机构名如 Политбюро→政治局、НКВД→内务人民委员部、"
    "НКИД→外交人民委员部；公文套语保持档案腔）；\n"
    "3) 把 en 切分为句子列表 en_sents，zh 切分为 zh_sents；\n"
    "4) 给出俄中句子对齐 align：[[俄句下标,中句下标],...]，允许一对多/多对一。\n"
    "硬性要求：\n"
    "- 每个对象的 key 必须**原样**保留我给出的标识；\n"
    "- en_sents 顺序首尾拼接必须**逐字符等于 en**；zh_sents 逐字符拼接等于 zh。为满足这点：\n"
    "   * 先完整写下 en，再从 en 里切句，每句必须能从 en 中连续取原词（含标点）；\n"
    "   * 先完整写下 zh，再从 zh 里切句；\n"
    "   * 切勿在 en 与 en_sents 之间、zh 与 zh_sents 之间改动任何词、空格或标点；\n"
    "- 中文句号用“。”；绝不截断；页码/文档编号/注号按原样放进 en 与对应句。\n"
    "自检：en_sents 用空串 join 后必须与 en 完全相同，否则修正后再输出。\n"
    "只输出一个 JSON 数组（不要 Markdown 代码块、不要任何解释），按给出顺序每段一个对象：\n"
    "{\"key\":\"标识\",\"en\":\"...\",\"zh\":\"...\",\"en_sents\":[...],\"zh_sents\":[...],\"align\":[[0,0],...]}\n\n"
    "段落如下：\n"
)

RAPID_SECS = set(x for x in os.environ.get('ECNU_RAPID_SECS', '').split(',') if x)


def build_trans_batch(items):
    ps = ''
    for key, text in items:
        ps += f"\n--- {key} ---\n{text}\n"
    return ("你是中英对照学术专著翻译专家。下面给出若干段英文（标题、参考文献条目、索引条目或简短文本）。"
            "请逐条翻译成简洁准确的中文（学术专著风格；人名地名机构名用通行译名；参考文献保留原文格式，"
            "只把可译部分译出，书名/篇名可保留英文原名并酌情加中文；索引条目译为中文并保留页码）。"
            "同时复原干净正确的英文 en（修正断字）。\n"
            "只输出一个 JSON 数组，不要 Markdown 代码块，按给出顺序每段一个对象：\n"
            "{\"key\":\"标识\",\"en\":\"...\",\"zh\":\"...\"}\n"
            "key 必须原样保留。\n" + ps)


TRANS_ONLY = (
    "你是中英对照学术专著翻译专家。把下面这段英文标题/小标题/简短文本翻译成通顺的中文"
    "（学术专著风格，尽量简洁忠实）。同时复原出干净正确的英文 en（若原文有断字错误请修正）。\n"
    "人名地名用通行译名：Chiang Kai-shek=蒋介石、Stilwell=史迪威、Chennault=陈纳德、"
    "Kunming=昆明、Chongqing=重庆、Guomindang=国民党。\n"
)

def build_trans_only(key, text):
    ru = re.search(r'[\u0400-\u04FF]', text)
    if ru:
        p = ("你是俄汉对照图书翻译专家。把下面这段俄文标题/小标题/简短文本翻译成通顺的中文"
             "（学术专著风格，尽量简洁忠实）。同时复原出干净正确的俄文 en（字段名沿用 en，实为俄文原文；"
             "若原文有OCR断词错误请修正）。\n"
             "只输出一个JSON对象（不要代码块）：{\"key\":\"标识\",\"en\":\"...\",\"zh\":\"...\"}\n"
             "段落标识key原样保留。\n\n")
    else:
        p = (TRANS_ONLY +
             "只输出一个JSON对象（不要代码块）：{\"key\":\"标识\",\"en\":\"...\",\"zh\":\"...\"}\n"
             "段落标识key原样保留。\n\n")
    return p + f"--- {key} ---\n{text}\n"

def main():
    data = json.load(open(EN_DATA, encoding='utf-8'))
    results = {}
    if os.path.exists(OUT):
        try:
            results = json.load(open(OUT, encoding='utf-8'))
        except Exception:
            results = {}

    # 收集待处理任务： (key, type, text)
    tasks = []
    for sec in data:
        sid = sec['id']
        for i, p in enumerate(sec['paras']):
            key = f"{sid}/{i}"
            if key in results:
                continue
            tasks.append((key, p['type'], p['text']))

    full = len(results)
    print(f"total sections={len(data)} tasks_todo={len(tasks)} already_done={full}", flush=True)

    # 拆成批次；h 用纯翻译 type=T，其余用 combined type=C
    batches = []
    for key, typ, text in tasks:
        sec = key.split('/')[0]
        rapid = sec in RAPID_SECS
        batches.append((('T' if (typ in ('h', 'subh') or rapid) else 'C'), key, text))
    # 合并连续同类型，按批打包
    chunked = []
    for kind, key, text in batches:
        if (chunked and chunked[-1][0] == kind and len(chunked[-1][1]) < (BATCH if kind == 'C' else 12)
                and chunked[-1][2] + len(text) <= BATCH_CHARS):
            chunked[-1][1].append((key, text)); chunked[-1][2] += len(text)
        else:
            chunked.append([kind, [(key, text)], len(text)])
    chunked = [(k, items) for k, items, _ in chunked]

    lock = threading.Lock()
    done_counter = [0]

    def worker(wid):
        while True:
            try:
                chunk = q.get_nowait()
            except Exception:
                return
            kind, items = chunk
            ok = 0
            time.sleep(CALL_DELAY)
            if kind == 'C' and len(items) > 1 and items[0] not in (None,):
                # 先尝试整批；失败则二分（由 process_c 递归处理）
                pass
            try:
                if kind == 'C':
                    prompt = build_combined(items)
                    raw = call_api(prompt, max_tokens=min(MAX_TOK, 9000 + 2200 * len(items)))
                    arr = parse_json(raw)
                    if not isinstance(arr, list):
                        arr = [arr]
                    # 按 key 匹配
                    for order, it in enumerate(arr):
                        if not isinstance(it, dict):
                            continue
                        key = it.get('key')
                        if not key:
                            cand = [k for k, _ in items if f"{k}" not in results]
                            key = cand[order] if order < len(cand) else None
                            if not key:
                                continue
                        base = f"{key}"
                        if base in results:
                            continue
                        with lock:
                            results[base] = {
                                'type': 'C', 'en': it.get('en', ''), 'zh': it.get('zh', ''),
                                'en_sents': it.get('en_sents', []), 'zh_sents': it.get('zh_sents', []),
                                'align': it.get('align', []),
                            }
                            json.dump(results, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
                            ok += 1
                            done_counter[0] += 1
                            if done_counter[0] % 10 == 0:
                                print(f"    >> cumulative done: {done_counter[0]+full}", flush=True)
                else:
                    # 纯翻译：批量提交（h/subh 与 rapid 节）
                    raw = call_api(build_trans_batch(items), max_tokens=min(MAX_TOK, 1200 + 900 * len(items)))
                    arr = parse_json(raw)
                    if not isinstance(arr, list):
                        arr = [arr]
                    kmap = {k: tx for k, tx in items}
                    for order, it in enumerate(arr):
                        if not isinstance(it, dict):
                            continue
                        key = it.get('key')
                        if key not in kmap:
                            cand = [k for k, _ in items if k not in results]
                            if order < len(cand):
                                key = cand[order]
                            else:
                                continue
                        with lock:
                            results[key] = {'type': 'T', 'en': it.get('en', kmap.get(key, '')),
                                            'zh': it.get('zh', '')}
                            json.dump(results, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
                            ok += 1
                            done_counter[0] += 1
            except Exception as e:
                print(f"  [w{wid}] batch failed ({len(items)} items): {str(e)[:100]}", flush=True)
                if kind == 'C' and len(items) > 1:
                    mid = len(items) // 2
                    q.put(('C', items[:mid])); q.put(('C', items[mid:]))
                else:
                    # 单条仍失败：退回只译不切句
                    if kind == 'C' and items:
                        k, tx = items[0]
                        try:
                            raw = call_api(build_trans_only(k, tx), max_tokens=4000)
                            it = parse_json(raw)
                            if isinstance(it, list) and it: it = it[0]
                            if isinstance(it, dict):
                                with lock:
                                    results[k] = {'type': 'C', 'en': it.get('en', tx),
                                                  'zh': it.get('zh', ''),
                                                  'en_sents': [it.get('en', tx)],
                                                  'zh_sents': [it.get('zh', '')],
                                                  'align': [[0, 0]]}
                                    json.dump(results, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
                        except Exception as e2:
                            print('     fallback failed', str(e2)[:80], flush=True)
            finally:
                time.sleep(0.3)

    import queue
    q = queue.Queue()
    for c in chunked:
        q.put(c)
    threads = [threading.Thread(target=worker, args=(k,), daemon=True) for k in range(NWORKERS)]
    for t in threads:
        t.start()
    while True:
        alive = any(t.is_alive() for t in threads)
        if not alive and q.empty():
            break
        time.sleep(8)
    print("ALL DONE total results:", len(results), flush=True)

def parse_json(content):
    # 容忍外层 ```json 包裹
    if content.startswith('```'):
        content = content.split('\n', 1)[1].rsplit('```', 1)[0].strip()
    try:
        return json.loads(content)
    except Exception:
        # 尝试提取第一个 [ 到最后一个 ]
        try:
            i = content.find('[')
            j = content.rfind(']')
            if i != -1 and j > i:
                return json.loads(content[i:j+1])
        except Exception:
            pass
        try:
            i = content.find('{')
            j = content.rfind('}')
            if i != -1 and j > i:
                return json.loads(content[i:j+1])
        except Exception:
            pass
        raise ValueError("JSON parse failed")

if __name__ == '__main__':
    main()