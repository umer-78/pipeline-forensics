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
  $('#stack').innerHTML = d.versions.map((v) => {
    const segs = CATS.map(([c, col]) => ({ c, col, n: v.blame[c] || 0 })).filter((x) => x.n);
    return `<div class="sbar"><div class="sname"><b>${esc(v.version)}</b> <span class="muted small">${pct(v.accuracy)} right · ${int(v.failures)} wrong</span>${v.stop.length ? ' <span class="pill no">stop "\\n\\n"</span>' : ''}</div>` +
      `<div class="strack">${segs.map((x) => `<span style="width:${(100 * x.n) / v.failures}%;background:${x.col}" title="${esc(x.c)}: ${x.n} (${pct(x.n / v.failures, 0)})"></span>`).join('')}</div></div>`;
  }).join('');
  legend($('#stackKey'), CATS.slice(1).map(([c, color]) => ({ name: c, color })));

  $('#regSub').textContent = `${R.base} → ${R.candidate}: GSM8K accuracy fell from ${pct(d.versions.find((v) => v.version === R.base).accuracy)} to ${pct(d.versions.find((v) => v.version === R.candidate).accuracy)}. The model did not get worse at arithmetic: the newer run was configured with a stop sequence, and the answers ended at the first blank line.`;
  $('#regOut').innerHTML = `<div>Questions that broke<b>${int(R.broke)}</b><span class="muted small">right before, wrong after</span></div>` +
    Object.entries(R.blame).map(([c, n]) => `<div>${esc(c)}<b>${int(n)}</b><span class="muted small">${pct(n / R.broke)}</span></div>`).join('') +
    `<div>Stop sequences<b>${R.stop.base.length ? esc(JSON.stringify(R.stop.base)) : 'none'} → ${esc(JSON.stringify(R.stop.candidate))}</b><span class="muted small">before → after</span></div>`;
  $('#examples').innerHTML = R.examples.map((e) => `<article class="q"><pre class="box">${esc(e.answer)}<span class="err">▌ cut here</span></pre>${e.then ? `<p class="small muted">How the older version's answer to the same question ended: “…${esc(e.then.trim())}”</p>` : ''}</article>`).join('');
  bars($('#inject'), inj.map(([fault, x]) => ({ label: fault, value: x.failed ? x.blamed_right / x.failed : 0, text: `${x.blamed_right}/${x.failed} (${x.injected} injected)`, title: `${fault}: ${x.injected} injected, ${x.failed} failed, ${x.blamed_right} blamed right` })), { max: 1 });
} catch (err) {
  fail(err);
}
