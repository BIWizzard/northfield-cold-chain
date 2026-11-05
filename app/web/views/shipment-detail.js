import brand from '../brand.js'
import SourcePath from './source-path.js'
import LoggerChart from './logger-chart.js'
import { COLUMNS, MONO } from './shipments.js'

export default {
  name: 'ShipmentDetailView',
  components: { SourcePath, LoggerChart },
  props: {
    shipmentId: String,
    detail: Object,
    loading: Boolean,
    error: String,
    backHref: String,
  },
  data() {
    // Every column of the row, so the page can be checked against the CSV.
    return { columns: COLUMNS }
  },
  methods: {
    isMono(column) {
      return MONO.includes(column)
    },
    // The carrier's name and the lane's route, looked up from carriers.csv and lanes.csv.
    note(match, column) {
      if (column === 'carrier_id' && match.carrier) return match.carrier.name
      if (column === 'lane_id' && match.lane) {
        const lane = match.lane
        return plantName(lane.origin) + ' to ' + lane.destination + ', ' + lane.transit_hours + ' h'
      }
      return ''
    },
  },
  template: `
    <a class="back-link" :href="backHref">← Back to shipments</a>
    <div class="page-head">
      <div>
        <h1 class="id">{{ shipmentId }}</h1>
        <p class="sub">Shipment fields and logger readings, as they are in the repo</p>
      </div>
      <div v-if="detail" class="sources">
        <source-path label="Reads" :path="detail.source" />
        <source-path label="Limits" :path="detail.thresholds_source" />
      </div>
    </div>

    <div v-if="error" class="panel"><p class="message">{{ error }}</p></div>
    <p v-else-if="loading || !detail" class="muted">Loading…</p>
    <div v-else class="stack">
      <article v-for="(match, index) in detail.matches" :key="index" class="panel">
        <dl class="fields">
          <div v-for="column in columns" :key="column" :class="{ wide: column === 'logger_file' }">
            <dt>{{ column }}</dt>
            <dd :class="{ mono: isMono(column) }">
              {{ match.row[column] }}
              <small v-if="note(match, column)">{{ note(match, column) }}</small>
            </dd>
          </div>
        </dl>

        <div class="sources"><source-path label="Logger" :path="match.logger.path" /></div>

        <p v-if="!match.logger.found" class="message">
          Logger file not found: <code>{{ match.logger.path }}</code>
        </p>
        <p v-else-if="match.logger.readings.length === 0" class="message">
          This logger file has no readings.
        </p>
        <template v-else>
          <p v-if="!match.limits" class="message">
            No limits for category "{{ match.row.product_category }}" in {{ detail.thresholds_source }}.
          </p>
          <logger-chart
            :readings="match.logger.readings"
            :limits="match.limits"
            :category="match.row.product_category"
            :title="'Temperature readings for ' + match.row.shipment_id"
          />
        </template>
      </article>
    </div>
  `,
}

// Plant names start with the company's short name; it's dropped to keep the lane note short.
function plantName(origin) {
  const prefix = brand.shortName + ' '
  return origin.startsWith(prefix) ? origin.slice(prefix.length) : origin
}
