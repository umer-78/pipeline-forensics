import { $, bars, esc, fail, int, kpis, legend, load, pct } from './kit.js';

const CATS = [
  ['prompt lost the question', 'var(--c5)', 'prompt'],
  ['stopped before stating an answer', 'var(--bad)', 'stop sequence'],
  ['hit the token limit', 'var(--c4)', 'token limit'],
  ['extracted the wrong number', 'var(--c2)', 'extraction'],
  ['wrong answer (every check passed)', 'var(--c6)', 'model'],
];
try {
  const d = await load();
  const R = d.regression, inj = Object.entries(d.injection);
  const [topCause, topN] = Object.entries(R.blame).sort((a, b) => b[1] - a[1])[0];
  kpis($('#kpis'), [
    { label: 'Model versions traced', value: String(d.versions.length), note: `${int(d.versions.reduce((a, v) => a + v.failures, 0))} wrong GSM8K answers, each blamed on a step` },
    { label: 'A 45-point regression', value: pct(topN / R.broke, 0), note: `of ${int(R.broke)} broken answers: ${topCause}` },
    { label: 'Faults blamed correctly', value: `${int(inj.reduce((a, [, x]) => a + x.blamed_right, 0))}/${int(inj.reduce((a, [, x]) => a + x.failed, 0))}`, note: 'five kinds injected into correct traces' },
    { label: 'Failures that were the model', value: pct(d.versions.find((v) => v.version === 'llama-3.1-70b-instruct').blame['wrong answer (every check passed)'] / d.versions.find((v) => v.version === 'llama-3.1-70b-instruct').failures, 0), note: 'Llama 3.1 70B; for Gemini 1.5 Flash 002, none' },
  ]);
  $('#pipe').innerHTML = ['prompt', 'generate (stop sequence, token limit)', 'extract', 'score'].map((s) => `<span class="step">${s}</span>`).join('<span class="muted">→</span>');
  // the chart: in the order traced, by accuracy, or by how much of the damage was the pipeline's
  const MODEL = 'wrong answer (every check passed)';
  const pipeFaults = (v) => v.failures - (v.blame[MODEL] || 0);
  const most = Math.max(...d.versions.map((v) => v.failures));
  const drawStack = () => {
    const list = [...d.versions];
    if ($('#sortBy').value === 'acc') list.sort((a, b) => b.accuracy - a.accuracy);
    if ($('#sortBy').value === 'pipe') list.sort((a, b) => pipeFaults(b) - pipeFaults(a));
    const byCount = $('#scale').value === 'count';
    $('#stack').innerHTML = list.map((v) => {
      const segs = CATS.map(([c, col]) => ({ c, col, n: v.blame[c] || 0 })).filter((x) => x.n);
      const whole = byCount ? most : v.failures;
      return `<div class="sbar"><div class="sname"><b>${esc(v.version)}</b> <span class="muted small">${pct(v.accuracy)} right · ${int(v.failures)} wrong · ${int(pipeFaults(v))} pipeline faults</span>${v.stop.length ? ' <span class="pill no">stop "\\n\\n"</span>' : ''}</div>` +
        `<div class="strack">${segs.map((x) => `<span style="width:${(100 * x.n) / whole}%;background:${x.col}" title="${esc(x.c)}: ${x.n} (${pct(x.n / v.failures, 0)})"></span>`).join('')}</div></div>`;
    }).join('');
  };
  $('#sortBy').addEventListener('change', drawStack);
  $('#scale').addEventListener('change', drawStack);
  drawStack();
  legend($('#stackKey'), CATS.slice(1).map(([c, color]) => ({ name: c, color })));

  $('#regSub').textContent = `${R.base} → ${R.candidate}: GSM8K accuracy fell from ${pct(d.versions.find((v) => v.version === R.base).accuracy)} to ${pct(d.versions.find((v) => v.version === R.candidate).accuracy)}. The model did not get worse at arithmetic: the newer run was configured with a stop sequence, and the answers ended at the first blank line.`;
  $('#regOut').innerHTML = `<div>Questions that broke<b>${int(R.broke)}</b><span class="muted small">right before, wrong after</span></div>` +
    Object.entries(R.blame).map(([c, n]) => `<div>${esc(c)}<b>${int(n)}</b><span class="muted small">${pct(n / R.broke)}</span></div>`).join('') +
    `<div>Stop sequences<b>${R.stop.base.length ? esc(JSON.stringify(R.stop.base)) : 'none'} → ${esc(JSON.stringify(R.stop.candidate))}</b><span class="muted small">before → after</span></div>`;
  $('#examples').innerHTML = R.examples.map((e) => `<article class="q"><pre class="box">${esc(e.answer)}<span class="err">▌ cut here</span></pre>${e.then ? `<p class="small muted">How the older version's answer to the same question ended: “…${esc(e.then.trim())}”</p>` : ''}</article>`).join('');
  // any two versions, side by side
  const options = d.versions.map((v, i) => `<option value="${i}">${esc(v.version)}</option>`).join('');
  $('#cmpA').innerHTML = options;
  $('#cmpB').innerHTML = options;
  $('#cmpA').value = String(d.versions.findIndex((v) => v.version === R.base));
  $('#cmpB').value = String(d.versions.findIndex((v) => v.version === R.candidate));
  const signed = (n) => (n > 0 ? `+${int(n)}` : n < 0 ? `−${int(-n)}` : '±0');
  const stops = (v) => (v.stop.length ? JSON.stringify(v.stop) : 'none');
  const drawCompare = () => {
    const a = d.versions[+$('#cmpA').value], b = d.versions[+$('#cmpB').value];
    const rows = CATS.map(([c]) => ({ c, x: a.blame[c] || 0, y: b.blame[c] || 0 }));
    const biggest = rows.reduce((m, r) => (Math.abs(r.y - r.x) > Math.abs(m.y - m.x) ? r : m));
    const points = (100 * (b.accuracy - a.accuracy)).toFixed(1);
    $('#cmpOut').innerHTML = `<div>Accuracy<b>${pct(a.accuracy)} → ${pct(b.accuracy)}</b><span class="muted small">${points > 0 ? '+' : ''}${points} points</span></div>` +
      `<div>Wrong answers<b>${int(a.failures)} → ${int(b.failures)}</b><span class="muted small">${signed(b.failures - a.failures)}</span></div>` +
      rows.map((r) => `<div${r === biggest && r.y !== r.x ? ' class="hl"' : ''}>${esc(r.c)}<b>${int(r.x)} → ${int(r.y)}</b><span class="muted small">${signed(r.y - r.x)}</span></div>`).join('');
    $('#cmpNote').textContent = a === b ? 'The same version is on both sides: pick two different ones.'
      : `Largest change: ${biggest.c} (${signed(biggest.y - biggest.x)}). Stop sequences: ${stops(a)} before, ${stops(b)} after.`;
  };
  $('#cmpA').addEventListener('change', drawCompare);
  $('#cmpB').addEventListener('change', drawCompare);
  $('#cmpSwap').addEventListener('click', () => {
    [$('#cmpA').value, $('#cmpB').value] = [$('#cmpB').value, $('#cmpA').value];
    drawCompare();
  });
  drawCompare();

  bars($('#inject'), inj.map(([fault, x]) => ({ label: fault, value: x.failed ? x.blamed_right / x.failed : 0, text: `${x.blamed_right}/${x.failed} (${x.injected} injected)`, title: `${fault}: ${x.injected} injected, ${x.failed} failed, ${x.blamed_right} blamed right` })), { max: 1 });
} catch (err) {
  fail(err);
}
