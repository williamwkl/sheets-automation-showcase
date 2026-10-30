/**
 * 20_ExternalPulls.gs — GA4 + Google Business Profile automated pulls.
 *
 * These are the two API integrations. In this sample they run against mock
 * "Raw_GA4" / "Raw_GBP" tabs so the whole pipeline is demonstrable without live
 * credentials; the functions are structured exactly as the production versions,
 * with the real API calls shown and gated behind Script-Property credentials.
 *
 * GA4:  GA4 Data API v1 (runReport) via a service account shared on the property
 *       — no OAuth consent screen to maintain. Free, well within quota for a few
 *       properties on a weekly cadence.
 * GBP:  Business Profile Performance API (the old GMB API was split into 8 APIs).
 *       That API is ACCESS-GATED (formal request + 60-day-verified profile +
 *       Google's manual review), so production has two modes: (a) direct API once
 *       access is granted, or (b) a connector bridge that writes GBP metrics into
 *       Raw_GBP under its own approved app, so the schedule is never blocked by
 *       Google's review queue. This code reads Raw_GBP either way.
 */

/**
 * Refresh both external feeds, then fold them into History for `week`.
 * `week` is passed by weeklyRefresh (the week that was just imported) so a
 * backfill of an OLDER week merges into that week, not the newest one. The menu
 * action calls it with no argument, where it targets the latest week.
 */
function refreshAll(week) {
  pullGA4_();          // no-op in mock mode unless credentials are set
  pullGBP_();          // connector or API writes Raw_GBP; here it's mock
  mergeExternalIntoHistory_(week);
}

/**
 * GA4 Data API pull. Production path shown; runs only when GA4_PROPERTY_ID +
 * a service-account key are present in Script Properties, else leaves the mock
 * Raw_GA4 tab in place so the demo still works.
 */
function pullGA4_() {
  const propertyId = getProp_(CONFIG.PROP_KEYS.GA4_PROPERTY, '');
  const saKey = getProp_(CONFIG.PROP_KEYS.GA4_SA_KEY, '');
  if (!propertyId || !saKey) {
    logInfo_('GA4: no credentials set — using mock Raw_GA4 (production uses the GA4 Data API).');
    return;
  }
  try {
    const token = serviceAccountToken_(JSON.parse(saKey),
      'https://www.googleapis.com/auth/analytics.readonly');
    const url = 'https://analyticsdata.googleapis.com/v1beta/properties/' + propertyId + ':runReport';
    // The property model is set per deployment: either one GA4 property per managed
    // property (loop property ids), or a single property with a dimension that
    // identifies the property (e.g. a custom dimension / hostname). Shape the
    // report to whatever your GA4 setup uses; this is the integration seam.
    const body = {
      dateRanges: [{ startDate: '7daysAgo', endDate: 'yesterday' }],
      dimensions: [{ name: 'hostName' }],          // placeholder — swap to your property identifier
      metrics: [{ name: 'sessions' }, { name: 'totalUsers' }, { name: 'conversions' }],
    };
    const res = UrlFetchApp.fetch(url, {
      method: 'post', contentType: 'application/json',
      headers: { Authorization: 'Bearer ' + token },
      payload: JSON.stringify(body), muteHttpExceptions: true,
    });
    if (res.getResponseCode() !== 200) {
      flagReview_(new Date(), '(GA4)', 'api error', 'GA4 Data API returned HTTP ' + res.getResponseCode());
      return;
    }
    const wrote = writeGA4Rows_(JSON.parse(res.getContentText()));   // maps response -> Raw_GA4
    if (wrote === 0) {
      flagReview_(new Date(), '(GA4)', 'not persisted',
        'GA4 Data API responded but no rows were mapped to Raw_GA4 — finalize the property mapping for this account.');
      return;
    }
    logInfo_('GA4: wrote ' + wrote + ' property row(s) to Raw_GA4.');
  } catch (err) {
    flagReview_(new Date(), '(GA4)', 'api error', String(err.message));
  }
}

/**
 * GBP metrics land in Raw_GBP — from the Business Profile Performance API once
 * access is approved, or from a connector in the meantime. This function is the
 * seam; the demo ships with a mock Raw_GBP already populated.
 */
function pullGBP_() {
  // Production: iterate locations, call the Performance API's fetchMultiDailyMetricsTimeSeries
  // for CALL_CLICKS, WEBSITE_CLICKS, BUSINESS_DIRECTION_REQUESTS, BUSINESS_IMPRESSIONS_*.
  // (Photo-view and search-term-split metrics were deprecated, so we don't request them.)
  logInfo_('GBP: reading Raw_GBP (API once access is approved, or connector bridge until then).');
}

/**
 * Fold the current Raw_GA4 + Raw_GBP snapshots into History for the latest week,
 * keyed by property. Idempotent — reuses the same upsert path as the Yardi import.
 */
function mergeExternalIntoHistory_(week) {
  const ss = SpreadsheetApp.getActive();
  week = week || latestHistoryWeek_(ss);           // explicit week wins (backfill-safe)
  if (!week) { logInfo_('External merge skipped: no Yardi week in History yet.'); return; }

  const ga4 = readNamedTable_(ss, CONFIG.SHEETS.GA4);   // {property -> {Sessions,Users,Conversions,Leads}}
  const gbp = readNamedTable_(ss, CONFIG.SHEETS.GBP);   // {property -> {Calls,...}}

  const patches = [];
  CONFIG.PROPERTIES.forEach(function (p) {
    const g = ga4[p.canonical] || {};
    const b = gbp[p.canonical] || {};
    patches.push({
      week_ending: week, property_id: p.id, Property: p.canonical,
      Sessions: g['Sessions'], Users: g['Users'], Conversions: g['Conversions'], Leads: g['Leads'],
      'GBP Calls': b['Calls'], 'GBP Website Clicks': b['Website Clicks'],
      'GBP Directions': b['Directions'], 'GBP Views': b['Views'],
    });
  });
  patchHistory_(patches);      // update only the columns supplied, keep Yardi fields intact
  logInfo_('External merge: GA4 + GBP folded into History for ' + fmtDate_(week) + '.');
}
