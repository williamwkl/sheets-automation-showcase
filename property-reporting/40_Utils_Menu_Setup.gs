/**
 * 40_Utils_Menu_Setup.gs — installer, menu, shared helpers, and self-tests.
 */

/* ---------- menu + scheduled entry point ---------- */

function onOpen() {
  SpreadsheetApp.getUi().createMenu('📊 Reporting')
    .addItem('Run setup / repair', 'setup')
    .addSeparator()
    .addItem('Import Yardi week', 'importYardiWeek')
    .addItem('Refresh GA4 + GBP', 'refreshAll')
    .addItem('Run full weekly refresh', 'weeklyRefresh')
    .addItem('Scan for anomalies', 'detectAnomalies')
    .addSeparator()
    .addItem('Run self-tests', 'runTests')
    .addToUi();
}

/** Public, locked Yardi import (menu + standalone). Returns the imported week. */
function importYardiWeek() {
  const lock = LockService.getScriptLock();
  lock.waitLock(30 * 1000);
  try { return importYardiWeek_(); } finally { lock.releaseLock(); }
}

/**
 * The scheduled job: one lock around the WHOLE weekly transaction so a manual and
 * a scheduled run can't interleave and clobber History. Aborts cleanly if the
 * Yardi import fails, so external metrics are never merged into the wrong week.
 */
function weeklyRefresh() {
  const lock = LockService.getScriptLock();
  lock.waitLock(5 * 60 * 1000);
  try {
    const week = importYardiWeek_();
    if (!week) { logInfo_('Weekly refresh ABORTED — Yardi import failed; external merge + anomaly scan skipped.'); return; }
    refreshAll(week);          // merge GA4/GBP into the exact week imported (backfill-safe)
    detectAnomalies(week);     // scan that same week
    logInfo_('Weekly refresh complete for ' + fmtDate_(week) + '.');
  } finally { lock.releaseLock(); }
}

/** Idempotent installer: ensures tabs exist and the weekly trigger is installed once. */
function setup() {
  const ss = SpreadsheetApp.getActive();
  Object.values(CONFIG.SHEETS).forEach(function (name) {
    if (!ss.getSheetByName(name)) ss.insertSheet(name);
  });
  const history = ss.getSheetByName(CONFIG.SHEETS.HISTORY);
  if (history.getLastRow() === 0) {
    history.appendRow(CONFIG.HISTORY_HEADERS);
    history.getRange(1, 1, 1, CONFIG.HISTORY_HEADERS.length).setFontWeight('bold');
    history.setFrozenRows(1);
  }
  ensureTrigger_('weeklyRefresh', function () {
    return ScriptApp.newTrigger('weeklyRefresh').timeBased().everyWeeks(1)
      .onWeekDay(ScriptApp.WeekDay.MONDAY).atHour(6).create();
  });
  logInfo_('setup() complete (v' + CONFIG.VERSION + ').');
  SpreadsheetApp.getActive().toast('Setup complete.', 'Reporting', 4);
}

function ensureTrigger_(handler, createFn) {
  const exists = ScriptApp.getProjectTriggers().some(function (t) { return t.getHandlerFunction() === handler; });
  if (!exists) createFn();
}

/* ---------- Review + logging ---------- */

function flagReview_(week, entity, check, detail) {
  try {
    const ss = SpreadsheetApp.getActive();
    const sheet = ss.getSheetByName(CONFIG.SHEETS.REVIEW) || ss.insertSheet(CONFIG.SHEETS.REVIEW);
    if (sheet.getLastRow() === 0) sheet.appendRow(['Week Ending', 'Property', 'Check', 'Detail']);
    sheet.appendRow([week || '', entity || '', check || '', detail || '']);
  } catch (err) { console.error('flagReview_ failed: ' + err.message); }
}

function logInfo_(msg) { console.log('[' + CONFIG.VERSION + '] ' + msg); }

function sendMail_(to, subject, html) {
  if (!to) return;
  if (CONFIG.DRY_RUN) { logInfo_('[DRY_RUN] would email: ' + subject); return; }
  try { MailApp.sendEmail({ to: to, subject: subject, htmlBody: html }); }
  catch (err) { console.error('sendMail_ failed: ' + err.message); }
}

/* ---------- History read helpers ---------- */

function latestHistoryWeek_(ss) {
  const sheet = mustSheet_(ss, CONFIG.SHEETS.HISTORY);
  const last = sheet.getLastRow();
  if (last < 2) return null;
  const weeks = sheet.getRange(2, 1, last - 1, 1).getValues();
  let best = null;
  weeks.forEach(function (r) { if (r[0] instanceof Date && (!best || r[0] > best)) best = r[0]; });
  return best;
}

function priorWeekDate_(ss, latest) {
  const sheet = mustSheet_(ss, CONFIG.SHEETS.HISTORY);
  const last = sheet.getLastRow();
  const weeks = sheet.getRange(2, 1, last - 1, 1).getValues();
  let best = null;
  weeks.forEach(function (r) {
    if (r[0] instanceof Date && r[0] < latest && (!best || r[0] > best)) best = r[0];
  });
  return best;
}

/** {property_id -> {header: value}} for one week. */
function weekByProperty_(ss, week) {
  const sheet = mustSheet_(ss, CONFIG.SHEETS.HISTORY);
  const headers = CONFIG.HISTORY_HEADERS;
  const last = sheet.getLastRow();
  const rows = last > 1 ? sheet.getRange(2, 1, last - 1, headers.length).getValues() : [];
  const out = {};
  rows.forEach(function (row) {
    if (row[0] instanceof Date && row[0].getTime() === week.getTime()) {
      const rec = {}; headers.forEach(function (h, i) { rec[h] = row[i]; });
      out[row[1]] = rec;                       // key by Property ID
    }
  });
  return out;
}

/** Read a small "Property + metrics" raw tab into {canonicalName -> {metric: value}}. */
function readNamedTable_(ss, name) {
  const sheet = mustSheet_(ss, name);
  const grid = sheet.getDataRange().getValues();
  const hdrRow = grid.findIndex(function (r) {
    return String(r[0]).trim().toLowerCase() === 'property';
  });
  if (hdrRow < 0) return {};
  const headers = grid[hdrRow].map(function (v) { return String(v).trim(); });
  const out = {};
  for (let r = hdrRow + 1; r < grid.length; r++) {
    const rawName = String(grid[r][0] || '').trim();
    if (!rawName) continue;
    const prop = matchProperty_(rawName);
    const key = prop ? prop.canonical : rawName;
    const rec = {};
    for (let c = 1; c < headers.length; c++) rec[headers[c]] = num_(grid[r][c]);
    out[key] = rec;
  }
  return out;
}

/** Patch only the supplied columns of matching History rows (keeps Yardi fields). */
function patchHistory_(patches) {
  const ss = SpreadsheetApp.getActive();
  const sheet = mustSheet_(ss, CONFIG.SHEETS.HISTORY);
  const headers = CONFIG.HISTORY_HEADERS;
  const last = sheet.getLastRow();
  if (last < 2) return;
  const rows = sheet.getRange(2, 1, last - 1, headers.length).getValues();
  const idx = {};
  rows.forEach(function (row, i) { idx[keyOf_(row[0], row[1])] = i; });
  patches.forEach(function (patch) {
    const i = idx[keyOf_(patch.week_ending, patch.property_id)];
    if (i === undefined) return;
    headers.forEach(function (h, c) {
      if (patch[h] !== undefined && patch[h] !== null && Number.isFinite(Number(patch[h]))) rows[i][c] = Number(patch[h]);
    });
  });
  sheet.getRange(2, 1, rows.length, headers.length).setValues(rows);
}

/**
 * Map a GA4 runReport response into Raw_GA4 (one row per canonical property) and
 * return the number of rows written. The row->property aggregation depends on the
 * client's GA4 setup (per-property properties, or a property-identifying
 * dimension), so this is finalized at deployment against the real account. In the
 * demo GA4 runs in mock mode, so this returns 0 and the mock Raw_GA4 stands.
 */
function writeGA4Rows_(apiResponse) {
  const rows = (apiResponse && apiResponse.rows) || [];
  logInfo_('GA4: response carried ' + rows.length + ' report rows (mapping finalized per your GA4 property model).');
  return 0;
}

/* ---------- service-account JWT (GA4) ---------- */

/** Mint an OAuth access token from a service-account key (RS256 JWT grant). */
function serviceAccountToken_(key, scope) {
  const now = Math.floor(Date.now() / 1000);
  const header = base64url_(JSON.stringify({ alg: 'RS256', typ: 'JWT' }));
  const claim = base64url_(JSON.stringify({
    iss: key.client_email, scope: scope, aud: 'https://oauth2.googleapis.com/token',
    iat: now, exp: now + 3600,
  }));
  const signature = Utilities.computeRsaSha256Signature(header + '.' + claim, key.private_key);
  const jwt = header + '.' + claim + '.' + base64url_(signature);
  const res = UrlFetchApp.fetch('https://oauth2.googleapis.com/token', {
    method: 'post', muteHttpExceptions: true,
    payload: { grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer', assertion: jwt },
  });
  if (res.getResponseCode() !== 200) {
    throw new Error('Token endpoint returned HTTP ' + res.getResponseCode() + ' (check the service-account key/scope).');
  }
  const token = JSON.parse(res.getContentText()).access_token;
  if (!token) throw new Error('Token endpoint returned no access_token.');
  return token;
}

function base64url_(data) {
  const bytes = (typeof data === 'string') ? Utilities.newBlob(data).getBytes() : data;
  return Utilities.base64EncodeWebSafe(bytes).replace(/=+$/, '');
}

/* ---------- tiny pure helpers ---------- */

function mustSheet_(ss, name) {
  const s = ss.getSheetByName(name);
  if (!s) throw new Error('Missing sheet "' + name + '". Run setup() first.');
  return s;
}
function num_(v) {
  if (v === '' || v === null || v === undefined) return NaN;
  const n = Number(String(v).replace(/[$,%\s]/g, ''));
  return Number.isFinite(n) ? n : NaN;
}
function startOfDay_(d) { const x = new Date(d); x.setHours(0, 0, 0, 0); return x; }
function parseDate_(v) { const d = new Date(v); return isNaN(d.getTime()) ? null : startOfDay_(d); }
function fmtDate_(d) { return Utilities.formatDate(d, Session.getScriptTimeZone(), 'yyyy-MM-dd'); }
function esc_(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

/* ---------- self-tests (pure logic; run from the menu) ---------- */

function runTests() {
  const results = [];
  const ok = function (name, cond) { results.push((cond ? 'PASS' : 'FAIL') + ' — ' + name); };

  ok('num_ strips $ and commas', num_('$1,240') === 1240);
  ok('num_ blank -> NaN', Number.isNaN(num_('')));
  ok('canonical match exact', matchProperty_('Riverside Commons').id === 'P2');
  ok('canonical match drifted name', matchProperty_('Oak Park Res.').id === 'P3');
  ok('canonical match trailing space', matchProperty_('Maple Grove Apartments ').id === 'P1');
  ok('unknown property -> null', matchProperty_('Somewhere Else') === null);
  ok('total row detected', isTotalRow_('TOTAL') && isTotalRow_(' grand total '));
  ok('total row not a property', !isTotalRow_('Maple Grove Apartments'));

  const hdr = ['Property', 'Units', 'Occupied', 'Leased', 'Move In', 'Some Extra Col'];
  const cm = mapColumns_(hdr);
  ok('column map by name (Occupied->idx 2)', cm['Occupied'] === 2);
  ok('column map maps property label', cm['property_name'] === 0);
  ok('column map ignores unknown column', Object.values(cm).indexOf(5) === -1);

  const grid = [['x'], ['Property', 'Units', 'Occupied'], ['A', 1, 1]];
  ok('header found by name (row 1)', findHeaderRow_(grid) === 1);
  ok('keyOf composite', keyOf_(new Date(2026, 7, 28), 'P1') === '2026-08-28|P1');  // local date avoids tz drift

  const msg = results.join('\n');
  Logger.log(msg);
  const failed = results.filter(function (r) { return r.indexOf('FAIL') === 0; }).length;
  SpreadsheetApp.getActive().toast(failed ? (failed + ' test(s) FAILED') : 'All ' + results.length + ' tests passed',
    'Self-tests', 6);
  return msg;
}
