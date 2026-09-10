"""Create an honest reading-scope index from the six independent source ledgers."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent


def first(record, keys, default=''):
    for key in keys:
        if key in record:
            return record[key]
    return default


def as_text(value):
    if isinstance(value, list):
        return '；'.join(as_text(v) for v in value)
    if isinstance(value, dict):
        return '；'.join(f'{key}: {as_text(val)}' for key, val in value.items())
    return str(value)


def collect():
    assignments = json.loads((HERE / 'assignments.json').read_text())['assignments']
    entries, origins = [], []
    for assignment in assignments:
        root, identity = Path(assignment['worktree']), assignment['id']
        path = root / 'experiments' / identity / 'literature.json'
        source = json.loads(path.read_text())
        papers = first(source, ('papers', 'sources', 'items'))
        assert papers, identity
        head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
        report = f'https://github.com/xiangguaguadadi-dot/cumcm2026-b/blob/{head}/experiments/{identity}/report.md'
        origins.append(dict(agent=identity, commit=head, source_path=str(path),
                            source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), report_url=report))
        for p in papers:
            url = first(p, ('url', 'original_url', 'pdf_url'))
            title = p['title']
            arxiv = re.search(r'arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})', url)
            # A normalized title also unifies author-site/PMLR copies with arXiv.
            key = re.sub(r'[^a-z0-9]', '', title.lower())
            reading = as_text(first(p, ('read', 'read_scope', 'read_range', 'actual_reading_scope', 'actual_reading')))
            mapping = as_text(first(p, ('implementation', 'adoption', 'code_mapping', 'implementation_mapping')))
            support = as_text(first(p, ('experiment_support', 'empirical_support',
                                        'experimental_support', 'experiment_link',
                                        'evidence_and_limits')))
            round_links = as_text(first(p, ('round_links', 'adopted_rounds')))
            not_adopted = as_text(first(p, ('not_adopted_reason', 'not_used', 'reason')))
            assert url and reading and mapping, (identity, title)
            entries.append(dict(agent=identity, id=p['id'], title=title, url=url,
                                normalized_title=key, arxiv=arxiv.group(1) if arxiv else None,
                                tier=first(p, ('tier', 'collection', 'layer')),
                                reading_scope=reading, inspiration=as_text(p['inspiration']),
                                implementation_mapping=mapping, experimental_support=support,
                                round_links=round_links, not_adopted_reason=not_adopted,
                                report_url=report))
    title_to_key = {}
    for entry in entries:
        if entry['arxiv']:
            title_to_key[entry['normalized_title']] = 'arxiv:' + entry['arxiv']
    for entry in entries:
        entry['dedup_key'] = title_to_key.get(entry['normalized_title'], 'title:' + entry['normalized_title'])
    distinct = len({e['dedup_key'] for e in entries})
    result = dict(note='Reading engagements are route-specific records, not a count of unique '
                       'papers fully read. Actual page/section scope is preserved. Root reviewed '
                       'the ledgers and reports, and does not claim to have reread every primary paper.',
                  engagements=len(entries), distinct_sources_by_arxiv_or_title=distinct,
                  origins=origins, entries=entries)
    (HERE / 'literature_index.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    lines = ['# 六路线文献阅读与实现索引', '',
             f'共 {len(entries)} 条按路线记录的阅读条目，按 arXiv 编号或标准化题名去重为 {distinct} 个来源。'
             '同一论文在不同路线的阅读范围分别保留；这些数字不表示每篇均全文深读，也不表示领域覆盖完整。', '',
             '以下内容来自各路线的实际阅读清单。主协调审阅了这些清单、完整报告和代码差异，'
             '没有把逐篇原文全部重新阅读一遍。本索引用于检索“读了哪里、受到什么启发、进入了哪里”；'
             '原论文证据、本题各轮结果、未采用理由与实验支持边界见对应完整报告。', '']
    for origin in origins:
        identity = origin['agent']
        part = [e for e in entries if e['agent'] == identity]
        core = sum(str(e['tier']).startswith('core') for e in part)
        lines += [f'## {identity}', '',
                  f'{len(part)} 个来源，其中 {core} 个标为关键正文阅读。'
                  f'[该路线完整报告]({origin["report_url"]})。', '']
        for i, e in enumerate(part, 1):
            lines += [f'### {i}. [{e["title"]}]({e["url"]})', '',
                      f'实际阅读范围（{e["tier"]}）：{e["reading_scope"]}', '',
                      f'启发：{e["inspiration"]}', '',
                      f'实现或未采用记录：{e["implementation_mapping"]}', '']
            for label, field in [('相关轮次', 'round_links'), ('本题实验支持与边界', 'experimental_support'),
                                 ('未采用或选择理由', 'not_adopted_reason')]:
                if e[field]:
                    lines += [f'{label}：{e[field]}', '']
    (HERE / 'LITERATURE_MAP.md').write_text('\n'.join(lines))
    return result


if __name__ == '__main__':
    data = collect()
    print(json.dumps({k: v for k, v in data.items() if k not in ('entries', 'origins')}, ensure_ascii=False))
