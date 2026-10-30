/**
 * 30_Anomaly.gs — the above-and-beyond that property managers actually act on.
 * After each refresh, compare the latest week to the prior week per property and
 * flag any monitored metric that dropped more than CONFIG.ANOMALY_DROP. Flags go
 * to the Review sheet and (optionally) an email digest — managers care about a
 * property's calls falling off far more than another historical chart.
 */

const MONITORED = ['GBP Calls', 'GBP Directions', 'Leads', 'Sessions'];

function detectAnomalies(week) {
  const ss = SpreadsheetApp.getActive();
  const latest = week || latestHistoryWeek_(ss);   // scan the week just refreshed (backfill-safe)
  if (!latest) return [];
  const prior = priorWeekDate_(ss, latest);
  if (!prior) { logInfo_('Anomaly scan: no prior week to compare.'); return []; }

  const cur = weekByProperty_(ss, latest);
  const prev = weekByProperty_(ss, prior);
  const found = [];

  CONFIG.PROPERTIES.forEach(function (p) {
    const a = cur[p.id], b = prev[p.id];
    if (!a || !b) return;
    MONITORED.forEach(function (m) {
      const now = Number(a[m]), was = Number(b[m]);
      if (!Number.isFinite(now) || !Number.isFinite(was) || was <= 0) return;
      const drop = (was - now) / was;
      if (drop > CONFIG.ANOMALY_DROP) {
        const pct = Math.round(drop * 100);
        flagReview_(latest, p.canonical, 'anomaly flag',
          m + ' down ' + pct + '% WoW (' + was + ' -> ' + now + ') — surfaced for review.');
        found.push({ property: p.canonical, metric: m, dropPct: pct, was: was, now: now });
      }
    });
  });

  if (found.length) emailAnomalies_(latest, found);
  logInfo_('Anomaly scan: ' + found.length + ' flag(s).');
  return found;
}

function emailAnomalies_(week, found) {
  const to = getProp_(CONFIG.PROP_KEYS.OPS_EMAIL, '');
  if (!to) return;
  const rows = found.map(function (f) {
    return '<tr><td>' + esc_(f.property) + '</td><td>' + esc_(f.metric) +
      '</td><td align="right" style="color:#7A1F0A">-' + f.dropPct + '%</td>' +
      '<td align="right">' + f.was + ' &rarr; ' + f.now + '</td></tr>';
  }).join('');
  const html =
    '<div style="font-family:Arial,sans-serif;max-width:560px">' +
    '<h2 style="color:#0F766E">Performance anomalies — week ending ' + fmtDate_(week) + '</h2>' +
    '<table cellpadding="6" style="border-collapse:collapse;width:100%">' +
    '<tr><th align="left">Property</th><th align="left">Metric</th><th>WoW</th><th>Change</th></tr>' +
    rows + '</table></div>';
  sendMail_(to, 'Property performance anomalies (' + found.length + ') — ' + fmtDate_(week), html);
}
