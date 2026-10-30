/**
 * 00_Config.gs — single source of truth.
 * Sheet names, the Yardi header map (by NAME, never by column position), the
 * canonical property lookup, and thresholds. Secrets (GA4 property id, service-
 * account key, any connector token) live in Script Properties, never in code.
 *
 * Multifamily reporting automation — sample by William L.
 */
const CONFIG = Object.freeze({
  VERSION: '1.0.0',
  DRY_RUN: false,                    // true = log instead of writing / emailing

  SHEETS: {
    HISTORY:  'History',             // append-only database (composite key below)
    YARDI:    'Raw_Yardi_Weekly',
    GA4:      'Raw_GA4',
    GBP:      'Raw_GBP',
    REVIEW:   'Review',              // exceptions land here, never silently dropped
    DASHBOARD:'Dashboard',
  },

  // Composite key that makes ingestion idempotent (re-run a week -> upsert, not dupe)
  KEY: ['week_ending', 'property_id'],

  // Columns the Yardi import owns. On a re-import of an existing week we update
  // ONLY these, so the GA4/GBP columns written by the external merge survive.
  YARDI_OWNED: [
    'Week Ending', 'Property ID', 'Property', 'Units', 'Occupied', 'Leased',
    'Move-ins', 'Move-outs', 'Delinquencies', 'Applications',
  ],

  // History column order (must match the sheet header row).
  HISTORY_HEADERS: [
    'Week Ending','Property ID','Property','Units','Occupied','Leased',
    'Move-ins','Move-outs','Delinquencies','Applications',
    'Sessions','Users','Conversions','Leads',
    'GBP Calls','GBP Website Clicks','GBP Directions','GBP Views',
  ],

  // Yardi report is messy: header is not on row 1, names drift, a TOTAL row trails.
  // We locate the header by matching these known labels, then map by name.
  YARDI: {
    HEADER_MATCH: ['property', 'units', 'occupied'],   // row containing all of these = header
    // report label (lowercased, trimmed) -> our History field
    FIELD_MAP: {
      'property': 'property_name',
      'units': 'Units',
      'occupied': 'Occupied',
      'leased': 'Leased',
      'move in': 'Move-ins',
      'move out': 'Move-outs',
      'delinq.': 'Delinquencies',
      'delinquencies': 'Delinquencies',
      'applications': 'Applications',
    },
    TOTAL_LABELS: ['total', 'grand total', 'portfolio total'],  // skip these rows
  },

  // Canonical property directory — normalises drifting names ("Oak Park Res." ->
  // "Oak Park Residences") and supplies the stable property_id used in the key.
  PROPERTIES: [
    { id: 'P1', canonical: 'Maple Grove Apartments', aliases: ['maple grove apartments','maple grove'] },
    { id: 'P2', canonical: 'Riverside Commons',       aliases: ['riverside commons','riverside'] },
    { id: 'P3', canonical: 'Oak Park Residences',     aliases: ['oak park residences','oak park res.','oak park res','oak park'] },
  ],

  // Validation thresholds
  ROWCOUNT_TOLERANCE: 0.30,          // flag if this week's property count swings >30% vs last
  ANOMALY_DROP: 0.20,                // flag a metric that drops >20% week-over-week

  PROP_KEYS: Object.freeze({
    OPS_EMAIL:      'OPS_EMAIL',      // digest / anomaly alerts
    GA4_PROPERTY:   'GA4_PROPERTY_ID',
    GA4_SA_KEY:     'GA4_SERVICE_ACCOUNT_KEY',   // JSON key, Script Properties only
  }),
});

function getProp_(k, d) {
  const v = PropertiesService.getScriptProperties().getProperty(k);
  return (v === null || v === undefined) ? d : v;
}
