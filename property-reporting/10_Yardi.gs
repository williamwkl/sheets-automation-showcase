/**
 * 10_Yardi.gs — the showpiece: parse the weekly Yardi report robustly.
 *
 * The report has NO API, its header is not on row 1, property names drift week to
 * week, and it carries a trailing TOTAL row. This reads the whole used range,
 * finds the header BY NAME, maps columns by name, normalises each property to its
 * canonical name + stable id, reconciles the property rows against the report's
 * own TOTAL row, and upserts into the History database by composite key so a
 * re-run of the same week updates rather than duplicates. Anything it can't
 * reconcile is routed to the Review sheet — never silently ingested.
 */

/**
 * Entry point: import the current weekly Yardi tab into History.
 * Returns the imported week (Date) on success, or null on a fatal failure — so
 * the caller (weeklyRefresh) knows exactly which week to merge/scan and can abort
 * cleanly. Caller holds the lock for the whole weekly transaction.
 */
function importYardiWeek_() {
  const ss = SpreadsheetApp.getActive();
  const src = mustSheet_(ss, CONFIG.SHEETS.YARDI);
  const grid = src.getDataRange().getValues();

  const weekEnding = findWeekEnding_(grid);
  if (!weekEnding) { flagReview_('', '(import)', 'parse error', 'Could not find a "Week ending" date in the Yardi report — nothing imported.'); return null; }

  const hdr = findHeaderRow_(grid);
  if (hdr < 0) { flagReview_(weekEnding, '(import)', 'parse error', 'Could not locate the Yardi header row by name — nothing imported.'); return null; }

  const colOf = mapColumns_(grid[hdr]);
  const parsed = [];
  const seenKeys = {};
  let reportTotal = null;
  let dupFatal = false;

  for (let r = hdr + 1; r < grid.length; r++) {
    const rawName = String(grid[r][colOf.property_name] || '').trim();
    if (!rawName) continue;                                     // blank spacer row
    if (isTotalRow_(rawName)) { reportTotal = readRow_(grid[r], colOf); continue; }

    const prop = matchProperty_(rawName);
    if (!prop) { flagReview_(weekEnding, rawName, 'unknown property', 'Not in the canonical directory; row skipped.'); continue; }

    const rec = readRow_(grid[r], colOf);
    rec.week_ending = weekEnding;
    rec.property_id = prop.id;
    rec.Property = prop.canonical;
    if (rawName !== prop.canonical) {
      flagReview_(weekEnding, rawName, 'name normalized', 'Matched "' + rawName + '" -> "' + prop.canonical + '".');
    }
    const k = keyOf_(weekEnding, prop.id);
    if (seenKeys[k]) {
      dupFatal = true;
      flagReview_(weekEnding, prop.canonical, 'duplicate row', 'Property appears more than once in this week\'s report — import aborted.');
      continue;
    }
    seenKeys[k] = true;
    parsed.push(rec);
  }

  const result = validateWeek_(weekEnding, parsed, reportTotal);
  if (dupFatal || result.fatal.length) {
    flagReview_(weekEnding, '(import)', 'ABORTED', (result.fatal.length + (dupFatal ? 1 : 0)) + ' fatal issue(s) — nothing written to History this run.');
    logInfo_('Yardi import ' + fmtDate_(weekEnding) + ' ABORTED (' + result.fatal.length + ' fatal).');
    return null;
  }
  const n = upsertHistory_(parsed);
  logInfo_('Yardi import ' + fmtDate_(weekEnding) + ': ' + n + ' rows upserted (' + result.warnings.length + ' warning(s)).');
  return weekEnding;
}

/* ---------- parsing helpers (pure where possible) ---------- */

function findWeekEnding_(grid) {
  for (let r = 0; r < Math.min(grid.length, 12); r++) {
    for (let c = 0; c < grid[r].length; c++) {
      if (String(grid[r][c]).trim().toLowerCase() === 'week ending') {
        const v = grid[r][c + 1];
        return v instanceof Date ? startOfDay_(v) : parseDate_(v);
      }
    }
  }
  return null;
}

function findHeaderRow_(grid) {
  const need = CONFIG.YARDI.HEADER_MATCH;
  for (let r = 0; r < grid.length; r++) {
    const cells = grid[r].map(function (v) { return String(v).trim().toLowerCase(); });
    if (need.every(function (label) { return cells.indexOf(label) !== -1; })) return r;
  }
  return -1;
}

/** Map each report label to a History field via CONFIG.YARDI.FIELD_MAP (by NAME). */
function mapColumns_(headerRow) {
  const map = {};
  headerRow.forEach(function (label, idx) {
    const key = String(label).trim().toLowerCase();
    const field = CONFIG.YARDI.FIELD_MAP[key];
    if (field) map[field] = idx;
  });
  return map;
}

function readRow_(row, colOf) {
  const rec = {};
  Object.keys(colOf).forEach(function (field) {
    const v = row[colOf[field]];
    rec[field] = (field === 'property_name') ? String(v).trim() : num_(v);
  });
  return rec;
}

function isTotalRow_(name) {
  const n = name.trim().toLowerCase();
  return CONFIG.YARDI.TOTAL_LABELS.indexOf(n) !== -1;
}

/** Normalise a drifting property name to {id, canonical} or null. */
function matchProperty_(rawName) {
  const n = rawName.trim().toLowerCase();
  return CONFIG.PROPERTIES.find(function (p) {
    return p.canonical.toLowerCase() === n || p.aliases.indexOf(n) !== -1;
  }) || null;
}

/* ---------- validation ---------- */

/**
 * Returns {fatal:[], warnings:[]}. Fatal issues abort the whole write (bad data
 * must not reach History); warnings are surfaced but don't block.
 */
function validateWeek_(weekEnding, parsed, reportTotal) {
  const fatal = [], warnings = [];
  const warn = function (entity, check, detail) { warnings.push(check); flagReview_(weekEnding, entity, check, detail); };
  const fail = function (entity, check, detail) { fatal.push(check); flagReview_(weekEnding, entity, check, detail); };

  // 1. count sanity vs the most recent prior week — compare UNIQUE property ids.
  const prior = priorWeekCount_(weekEnding);
  const nUnique = parsed.length;   // already deduped by key in the caller
  if (prior > 0) {
    const swing = Math.abs(nUnique - prior) / prior;
    if (swing > CONFIG.ROWCOUNT_TOLERANCE) {
      warn('(row count)', 'count swing',
        nUnique + ' properties this week vs ' + prior + ' last week (' + Math.round(swing * 100) + '%) — verify completeness.');
    }
  }
  // 2. required fields + impossible values (impossible = fatal for that row's week)
  parsed.forEach(function (rec) {
    ['Units', 'Occupied'].forEach(function (f) {
      if (!Number.isFinite(rec[f])) fail(rec.Property, 'missing value', 'Field "' + f + '" is blank/non-numeric.');
    });
    if (Number.isFinite(rec.Occupied) && Number.isFinite(rec.Units) && rec.Occupied > rec.Units) {
      fail(rec.Property, 'impossible value', 'Occupied (' + rec.Occupied + ') > Units (' + rec.Units + ').');
    }
  });
  // 3. reconcile to the report's own TOTAL row. A present-but-mismatched total is
  //    fatal; a missing total is a warning (can't verify).
  if (reportTotal && Number.isFinite(reportTotal.Units)) {
    const allFinite = parsed.every(function (r) { return Number.isFinite(r.Units); });
    const sum = parsed.reduce(function (a, r) { return a + (Number.isFinite(r.Units) ? r.Units : 0); }, 0);
    if (!allFinite) {
      fail('(report total)', 'reconciliation FAILED', 'A property Units value is non-numeric, so the total cannot be reconciled.');
    } else if (sum !== reportTotal.Units) {
      fail('(report total)', 'reconciliation FAILED', 'Sum of property units (' + sum + ') != Yardi TOTAL (' + reportTotal.Units + ').');
    } else {
      flagReview_(weekEnding, '(report total)', 'reconciliation OK', 'Sum of property rows == Yardi TOTAL (units ' + sum + ').');
    }
  } else {
    warn('(report total)', 'no total row', 'No usable TOTAL row found — imported without a reconciliation check.');
  }
  return { fatal: fatal, warnings: warnings };
}

/* ---------- History upsert (idempotent by composite key) ---------- */

function upsertHistory_(records) {
  const ss = SpreadsheetApp.getActive();
  const sheet = mustSheet_(ss, CONFIG.SHEETS.HISTORY);
  const headers = CONFIG.HISTORY_HEADERS;
  const owned = CONFIG.YARDI_OWNED;             // columns Yardi may overwrite
  const last = sheet.getLastRow();
  const existing = last > 1 ? sheet.getRange(2, 1, last - 1, headers.length).getValues() : [];

  const idx = {};
  existing.forEach(function (row, i) { idx[keyOf_(row[0], row[1])] = i; });

  const applyOwned = function (row, rec) {
    headers.forEach(function (h, c) { if (owned.indexOf(h) !== -1) row[c] = histValue_(h, rec); });
  };
  const toAppend = [];
  const staged = {};            // key -> index into toAppend
  records.forEach(function (rec) {
    const k = keyOf_(rec.week_ending, rec.property_id);
    if (idx[k] !== undefined) {
      applyOwned(existing[idx[k]], rec);                 // update owned cols, keep GA4/GBP
    } else if (staged[k] !== undefined) {
      applyOwned(toAppend[staged[k]], rec);              // same key twice this run -> merge, don't re-append
    } else {
      const rowArr = headers.map(function (h) { return histValue_(h, rec); });
      staged[k] = toAppend.push(rowArr) - 1;
    }
  });

  if (existing.length) sheet.getRange(2, 1, existing.length, headers.length).setValues(existing);
  if (toAppend.length) sheet.getRange(sheet.getLastRow() + 1, 1, toAppend.length, headers.length).setValues(toAppend);
  return records.length;
}

function histValue_(header, rec) {
  switch (header) {
    case 'Week Ending': return rec.week_ending;
    case 'Property ID': return rec.property_id;
    case 'Property':    return rec.Property;
    default:            return Number.isFinite(rec[header]) ? rec[header] : '';
  }
}

function keyOf_(week, propId) {
  const w = week instanceof Date ? fmtDate_(week) : String(week);
  return w + '|' + String(propId);
}

/** Count of UNIQUE properties in the most recent week strictly before weekEnding. */
function priorWeekCount_(weekEnding) {
  const sheet = mustSheet_(SpreadsheetApp.getActive(), CONFIG.SHEETS.HISTORY);
  const last = sheet.getLastRow();
  if (last < 2) return 0;
  const rows = sheet.getRange(2, 1, last - 1, 2).getValues();   // [week, property_id]
  const target = weekEnding.getTime();
  let bestTime = -1;
  rows.forEach(function (r) {
    if (r[0] instanceof Date && r[0].getTime() < target && r[0].getTime() > bestTime) bestTime = r[0].getTime();
  });
  if (bestTime < 0) return 0;
  const ids = {};
  rows.forEach(function (r) { if (r[0] instanceof Date && r[0].getTime() === bestTime) ids[r[1]] = true; });
  return Object.keys(ids).length;
}
