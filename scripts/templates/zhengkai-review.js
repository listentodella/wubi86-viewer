(() => {
  'use strict';
  const report = JSON.parse(document.getElementById('review-data').textContent);
  const rows = report.rows;
  const byId = new Map(rows.map(row => [row.id, row]));
  const storageKey = `zhengkai-review-v1:${report.key}`;
  const decisions = Object.create(null);
  const fitChoices = new Map();
  const rowElements = new Map();
  let activeId = null;
  let visibleIds = [];
  let filter = 'pending';
  let filterMembers = new Set();
  let feedbackTimer;
  const $ = id => document.getElementById(id);
  const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const labels = {missing: '正楷缺字', structure: '结构待核对', style: '风格对照', reviewed: '已有人工确认'};
  const qualityLabels = {source: '原始拆分', whole: '成字字根', exact: '精确推断', approx: '近似推断', search: '取笔搜索'};

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function button(text, className, onClick) {
    const node = element('button', className, text);
    node.type = 'button';
    node.addEventListener('click', onClick);
    return node;
  }
  function art(svg, className = 'art') {
    const node = element('div', className);
    // SVG comes only from the embedded generator report, never imported judgments.
    if (svg) node.innerHTML = svg;
    else node.append(element('span', 'glyph-missing', '?'));
    return node;
  }
  function figure(caption, svg, className) {
    const fig = element('figure');
    fig.append(art(svg, className || 'art'), element('figcaption', '', caption));
    return fig;
  }
  function notice(text) {
    $('storage-notice').textContent = text;
    $('storage-notice').hidden = false;
  }
  function feedback(text) {
    clearTimeout(feedbackTimer);
    $('feedback').textContent = text;
    $('feedback').hidden = false;
    feedbackTimer = setTimeout(() => { $('feedback').hidden = true; }, 4000);
  }
  function exportValue() {
    return {version: 1, key: report.key, reportId: report.reportId, decisions: {...decisions}};
  }
  function exportText() {
    return JSON.stringify(exportValue(), null, 2) + '\n';
  }
  function validateImport(value) {
    if (!isObject(value) || value.version !== 1 || value.key !== report.key || value.reportId !== report.reportId || !isObject(value.decisions)) {
      throw new Error('判断文件不属于这份报告，或格式不正确。请使用本页下载的 JSON。');
    }
    const valid = Object.create(null);
    for (const [id, decision] of Object.entries(value.decisions)) {
      const row = byId.get(id);
      if (!row || !isObject(decision) || !['candidate', 'keep', 'defer', 'pending'].includes(decision.action)) {
        throw new Error(`无效的字根或判断：${id}`);
      }
      if (decision.note !== undefined && typeof decision.note !== 'string') throw new Error(`${id} 的备注必须是文字。`);
      const clean = {action: decision.action, note: decision.note || ''};
      if (decision.action === 'candidate') {
        if (typeof decision.candidateId !== 'string' || !row.candidates.some(c => c.id === decision.candidateId) || typeof decision.fit !== 'boolean') {
          throw new Error(`${id} 的候选编号或槽位适配选项无效。`);
        }
        clean.candidateId = decision.candidateId;
        clean.fit = decision.fit;
      }
      if (decision.action === 'keep' && !row.current.present) throw new Error(`${id} 正楷缺字，不能保留。`);
      valid[id] = clean;
    }
    return valid;
  }
  function persist() {
    try {
      localStorage.setItem(storageKey, JSON.stringify({reportId: report.reportId, decisions}));
    } catch {
      notice('浏览器无法保存 localStorage。页面仍可审阅，请下载判断 JSON 以免进度丢失。');
    }
  }
  function restore() {
    try {
      const raw = localStorage.getItem(storageKey);
      if (!raw) return;
      const saved = JSON.parse(raw);
      if (!isObject(saved) || saved.reportId !== report.reportId) {
        notice('检测到旧报告的浏览器判断，本页未套用。数据或字体已变化，请重新审阅；旧 JSON 不会自动应用。');
        return;
      }
      Object.assign(decisions, validateImport({...saved, version: 1, key: report.key}));
    } catch {
      notice('本地判断无法读取，未套用任何旧答案。可导入有效的备份 JSON，或重新审阅。');
    }
  }
  function isConfirmed(row) {
    const decision = decisions[row.id];
    return decision ? ['candidate', 'keep'].includes(decision.action) : Boolean(row.approved);
  }
  function updateSummary() {
    const confirmed = rows.filter(isConfirmed).length;
    const deferred = rows.filter(row => decisions[row.id]?.action === 'defer').length;
    const judged = confirmed + deferred;
    $('progress-count').textContent = `${judged} / ${rows.length}`;
    $('review-progress').max = rows.length;
    $('review-progress').value = judged;
    $('progress-caption').textContent = `已确定 ${confirmed} · 待补 ${deferred}。本地保存，建议下载 JSON 备份。`;
    $('pending-count').textContent = rows.length - confirmed;
    $('missing-count').textContent = report.summary.missing;
    $('structure-count').textContent = report.summary.structure;
  }
  function markActive(id, scroll = false) {
    if (!byId.has(id) || !visibleIds.includes(id)) return;
    activeId = id;
    for (const [root, node] of rowElements) node.classList.toggle('active', root === id);
    $('active-caption').textContent = `当前 ${id.toUpperCase()} · 1/2/3 选择 · J/K 移动`;
    if (scroll) rowElements.get(id).scrollIntoView({block: 'start', behavior: 'instant'});
  }
  function updateRow(id) {
    const row = byId.get(id);
    const node = rowElements.get(id);
    const decision = decisions[id];
    const state = node.querySelector('.decision-badge');
    state.className = 'badge decision-badge';
    if (decision?.action === 'candidate') {
      const index = row.candidates.findIndex(c => c.id === decision.candidateId);
      state.textContent = `已选 ${'ABC'[index]} · 未应用`;
      state.classList.add('selected');
    } else if (decision?.action === 'keep') {
      state.textContent = '已选保留 · 未应用'; state.classList.add('selected');
    } else if (decision?.action === 'defer') {
      state.textContent = '待补'; state.classList.add('deferred');
    } else {
      state.textContent = row.approved ? '项目已确认' : '待审';
    }
    for (const card of node.querySelectorAll('.candidate')) {
      const chosen = decision?.action === 'candidate' && decision.candidateId === card.dataset.candidate;
      card.classList.toggle('chosen', chosen);
      const choice = card.querySelector('[data-choice]');
      choice.setAttribute('aria-pressed', String(chosen));
      choice.textContent = chosen ? `✓ 已选择 ${choice.dataset.letter}` : `选择 ${choice.dataset.letter}`;
    }
    node.querySelector('[data-action="keep"]').setAttribute('aria-pressed', String(decision?.action === 'keep'));
    node.querySelector('[data-action="defer"]').setAttribute('aria-pressed', String(decision?.action === 'defer'));
    const fit = fitChoices.get(id) ?? true;
    node.querySelector('[data-fit]').checked = fit;
    for (const card of node.querySelectorAll('.candidate')) {
      const candidate = row.candidates.find(c => c.id === card.dataset.candidate);
      const preview = card.querySelector('.placement-art');
      preview.innerHTML = fit ? candidate.fittedSvg : candidate.rawSvg;
      card.querySelector('.placement-caption').textContent = fit ? '字体位置 · 适配原槽位' : '字体位置 · 保留原位置';
    }
    const notes = node.querySelector('textarea');
    if (notes.value !== (decision?.note || '')) notes.value = decision?.note || '';
  }
  function choose(id, action, candidateId) {
    const row = byId.get(id);
    if (action === 'keep' && !row.current.present) {
      feedback(`${id.toUpperCase()} 正楷缺字，请选择候选或标为待补。`); return;
    }
    const note = decisions[id]?.note || '';
    decisions[id] = {action, note};
    if (action === 'candidate') {
      decisions[id].candidateId = candidateId;
      decisions[id].fit = fitChoices.get(id) ?? true;
    }
    persist();
    updateRow(id);
    updateSummary();
    markActive(id);
    feedback(`${id.toUpperCase()} 判断已保存到浏览器，尚未改动项目字体。`);
    // Filter membership stays stable until the user explicitly changes filters.
  }
  function createRow(row) {
    const node = element('section', 'root-row');
    node.dataset.root = row.id;
    node.id = `root-${row.id}`;
    node.setAttribute('aria-labelledby', `title-${row.id}`);
    const header = element('header', 'row-header');
    const title = element('h2'); title.id = `title-${row.id}`;
    title.append(element('span', 'root-id', row.id.toUpperCase()), element('span', 'root-label', row.label));
    const badges = element('div', 'row-badges');
    badges.append(element('span', `badge ${row.category}`, labels[row.category] || '对照'), element('span', 'badge decision-badge', '待审'));
    header.append(title, badges);
    const reasons = element('div', 'reasons');
    for (const text of row.reasons) reasons.append(element('p', '', text));
    if (row.duplicates?.length) reasons.append(element('p', '', `黑体近似编号：${row.duplicates.map(id => id.toUpperCase()).join('、')}（仅提示，不自动合并）`));
    const content = element('div', 'root-content');
    const reference = element('div', 'reference');
    const referenceGrid = element('div', 'reference-grid');
    const blackCaption = row.blackReference && row.blackReference !== row.id ? `黑体参考 ${row.blackReference.toUpperCase()}` : '黑体原形';
    referenceGrid.append(figure(blackCaption, row.blackSvg), figure('当前正楷', row.current.svg));
    const referenceMeta = element('div', 'reference-meta');
    referenceMeta.append(element('div', '', row.current.present ? `现用：${row.current.label}${row.current.strokeCount ? ` · ${row.current.strokeCount} 笔` : ''}` : '当前正楷缺字'),
      element('div', '', `可取笔 ${row.stats.available} 组 · 比较 ${row.stats.compared} 组`));
    reference.append(referenceGrid, referenceMeta);
    const candidateGrid = element('div', 'candidate-grid');
    if (!row.candidates.length) candidateGrid.append(element('p', 'no-candidates', '没有可用候选，请标为待补并留下来源建议。'));
    row.candidates.forEach((candidate, index) => {
      const letter = 'ABC'[index];
      const card = element('article', 'candidate'); card.dataset.candidate = candidate.id;
      const top = element('div', 'candidate-top');
      top.append(element('span', 'candidate-letter', letter), element('span', 'candidate-source', `取自「${candidate.source}」`),
        element('span', 'candidate-quality', qualityLabels[candidate.quality] || candidate.quality));
      const meta = element('div', 'candidate-meta');
      meta.append(element('strong', '', `第 ${candidate.strokeText} 笔 · 共 ${candidate.strokes.length} 笔`),
        element('div', '', `形状参考 ${candidate.score.toFixed(3)} · 同形 ${candidate.support} 组`));
      const select = button(`选择 ${letter}`, 'candidate-select', () => choose(row.id, 'candidate', candidate.id));
      select.dataset.choice = candidate.id; select.dataset.letter = letter;
      select.setAttribute('aria-pressed', 'false');
      select.setAttribute('aria-label', `${row.id.toUpperCase()} 选择候选 ${letter}：${candidate.source} 第 ${candidate.strokeText} 笔`);
      const details = element('details');
      details.append(element('summary', '', '查看源字高亮与字体位置'));
      const detailContent = element('div', 'candidate-details');
      const source = figure(`源字 ${candidate.source} · 橙色为笔序`, candidate.sourceSvg);
      const placement = element('figure');
      placement.append(art(candidate.fittedSvg, 'art placement-art'), element('figcaption', 'placement-caption', '字体位置 · 适配原槽位'));
      detailContent.append(source, placement);
      const warnings = element('div', 'candidate-warnings');
      warnings.append(element('div', 'muted', `容差 F1 ${candidate.f1.toFixed(3)} · IoU ${candidate.iou.toFixed(3)} · 结构 ${candidate.shape.toFixed(3)}`));
      for (const text of candidate.warnings) warnings.append(element('div', '', text));
      detailContent.append(warnings); details.append(detailContent);
      card.append(top, art(candidate.shapeSvg, 'art shape-art'), meta, select, details);
      candidateGrid.append(card);
    });
    content.append(reference, candidateGrid);
    const controls = element('div', 'row-controls');
    const keep = button('保留当前', 'decision-action', () => choose(row.id, 'keep'));
    keep.dataset.action = 'keep'; keep.disabled = !row.current.present;
    keep.setAttribute('aria-label', `${row.id.toUpperCase()} 保留当前正楷`);
    const defer = button('都不对 / 待补', 'decision-action', () => choose(row.id, 'defer'));
    defer.dataset.action = 'defer'; defer.setAttribute('aria-label', `${row.id.toUpperCase()} 都不对 / 待补`);
    const clear = button('清除判断', 'quiet', () => {
      delete decisions[row.id]; fitChoices.set(row.id, true);
      persist(); updateRow(row.id); updateSummary(); feedback(`${row.id.toUpperCase()} 已清除浏览器判断，项目映射未改动。`);
    });
    clear.setAttribute('aria-label', `${row.id.toUpperCase()} 清除判断`);
    const fitLabel = element('label', 'fit-control');
    const fit = element('input'); fit.type = 'checkbox'; fit.checked = true; fit.dataset.fit = 'true';
    fit.setAttribute('aria-label', `${row.id.toUpperCase()} 适配原槽位`);
    fit.addEventListener('change', () => {
      fitChoices.set(row.id, fit.checked);
      if (decisions[row.id]?.action === 'candidate') {
        decisions[row.id].fit = fit.checked; persist();
      }
      updateRow(row.id);
    });
    fitLabel.append(fit, element('span', '', '适配原槽位'));
    const notesLabel = element('label', 'notes');
    const notes = element('textarea'); notes.rows = 1; notes.placeholder = '备注、疑似重复或补充来源…';
    notes.setAttribute('aria-label', `${row.id.toUpperCase()} 备注`);
    notes.addEventListener('input', () => {
      if (!decisions[row.id]) decisions[row.id] = {action: 'pending', note: ''};
      decisions[row.id].note = notes.value; persist();
    });
    notesLabel.append(element('span', '', '备注'), notes);
    controls.append(keep, defer, clear, fitLabel, notesLabel);
    node.append(header, reasons, content, controls);
    node.addEventListener('pointerdown', () => markActive(row.id));
    node.addEventListener('focusin', () => markActive(row.id));
    return node;
  }
  function resetFilterMembers() {
    filterMembers = new Set(rows.filter(row => {
      if (filter === 'pending') return !isConfirmed(row);
      if (filter === 'confirmed') return isConfirmed(row);
      if (filter === 'missing') return !row.current.present;
      return true;
    }).map(row => row.id));
  }
  function renderList(refreshMembers = false) {
    if (refreshMembers) resetFilterMembers();
    const search = $('root-search').value.trim().toLowerCase();
    const order = $('root-order').value;
    const priorities = {missing: 0, structure: 1, style: 2, reviewed: 3};
    const visible = rows.filter(row => filterMembers.has(row.id) && (!search ||
      [row.id, row.label, ...row.candidates.map(c => c.source)].some(value => value.toLowerCase().includes(search))));
    visible.sort((a, b) => (order === 'priority' ? (priorities[a.category] ?? 2) - (priorities[b.category] ?? 2) : 0) || parseInt(a.id, 16) - parseInt(b.id, 16));
    visibleIds = visible.map(row => row.id);
    const hiddenRows = rows.filter(row => !visibleIds.includes(row.id));
    for (const row of hiddenRows) rowElements.get(row.id).hidden = true;
    for (const row of visible) {
      const node = rowElements.get(row.id); node.hidden = false; $('root-list').append(node);
    }
    $('visible-caption').textContent = `展示 ${visible.length} / ${rows.length} 个字根 · 编号始终不变`;
    $('empty-state').hidden = visible.length !== 0;
    if (!visibleIds.includes(activeId)) activeId = visibleIds[0] || null;
    if (activeId) markActive(activeId);
    else $('active-caption').textContent = '暂无可见字根';
    for (const btn of document.querySelectorAll('[data-filter]')) btn.setAttribute('aria-pressed', String(btn.dataset.filter === filter));
  }

  restore();
  document.title = `${report.key.toUpperCase()} 键 · 正楷初审`;
  $('page-title').textContent = document.title;
  $('report-caption').textContent = `报告 ${report.reportId.slice(0, 12)} · 所有选择均需人工确认`;
  for (const [key, label] of [['generate', '生成报告'], ['dryRun', '只预览'], ['apply', '显式写入'], ['build', '重建字体']]) {
    const command = element('div', 'command-line');
    command.append(element('span', '', label), element('code', '', report.commands[key]));
    $('help-commands').append(command);
  }
  for (const row of rows) {
    fitChoices.set(row.id, decisions[row.id]?.action === 'candidate' ? decisions[row.id].fit : true);
    const node = createRow(row); rowElements.set(row.id, node); $('root-list').append(node);
    updateRow(row.id);
  }
  updateSummary(); renderList(true);
  for (const btn of document.querySelectorAll('[data-filter]')) btn.addEventListener('click', () => {
    filter = btn.dataset.filter; renderList(true);
  });
  $('root-search').addEventListener('input', () => renderList());
  $('root-order').addEventListener('change', () => renderList());
  $('show-all').addEventListener('click', () => { filter = 'all'; $('root-search').value = ''; renderList(true); });
  $('download-decisions').addEventListener('click', () => {
    const url = URL.createObjectURL(new Blob([exportText()], {type: 'application/json'}));
    const link = element('a'); link.href = url; link.download = `zhengkai-review-${report.key}.json`;
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    feedback('已下载判断 JSON。文件仅记录选择，不会自动写入项目。');
  });
  $('copy-decisions').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(exportText()); feedback('判断 JSON 已复制，可贴回对话或保存成文件。');
    } catch {
      $('copy-text').value = exportText(); $('copy-dialog').showModal(); $('copy-text').focus(); $('copy-text').select();
    }
  });
  $('import-decisions').addEventListener('change', async event => {
    const file = event.target.files[0];
    if (!file) return;
    try {
      const imported = validateImport(JSON.parse(await file.text()));
      Object.assign(decisions, imported);
      for (const id of Object.keys(imported)) {
        if (decisions[id].action === 'candidate') fitChoices.set(id, decisions[id].fit);
        updateRow(id);
      }
      persist(); updateSummary(); renderList(true);
      feedback(`已导入 ${Object.keys(imported).length} 行判断。尚未改动项目字体。`);
    } catch (error) {
      feedback(`导入失败，未改变判断：${error.message}`);
    } finally {
      event.target.value = '';
    }
  });
  $('reset-decisions').addEventListener('click', () => {
    if (!confirm('只清除当前按键的浏览器判断？项目字体与人工确认表不会改变。')) return;
    for (const id of Object.keys(decisions)) delete decisions[id];
    for (const row of rows) { fitChoices.set(row.id, true); updateRow(row.id); }
    persist(); updateSummary(); renderList(true); feedback('已重置本页浏览器判断，项目文件未改动。');
  });
  document.addEventListener('keydown', event => {
    if (event.ctrlKey || event.metaKey || event.altKey || event.isComposing || $('copy-dialog').open) return;
    const focused = document.activeElement;
    if (focused?.matches('input,textarea,select') || focused?.isContentEditable) return;
    const key = event.key.toLowerCase();
    if (['j', 'k', 'arrowdown', 'arrowup'].includes(key)) {
      if (!visibleIds.length) return;
      event.preventDefault();
      const step = ['j', 'arrowdown'].includes(key) ? 1 : -1;
      const next = Math.max(0, Math.min(visibleIds.length - 1, visibleIds.indexOf(activeId) + step));
      markActive(visibleIds[next], true); return;
    }
    if (!activeId) return;
    if (['1', '2', '3'].includes(key)) {
      const candidate = byId.get(activeId).candidates[Number(key) - 1];
      if (candidate) { event.preventDefault(); choose(activeId, 'candidate', candidate.id); }
    } else if (key === '0') {
      event.preventDefault(); choose(activeId, 'keep');
    } else if (key === 'x') {
      event.preventDefault(); choose(activeId, 'defer');
    }
  });
})();
