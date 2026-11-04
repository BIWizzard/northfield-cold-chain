import SourcePath from './source-path.js'
import LoggerChart from './logger-chart.js'
import { COLUMNS } from './shipments.js'

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
    return { columns: COLUMNS }
  },
  template: `
    <section class="panel">
      <a class="back-link" :href="backHref">← Back to shipments</a>
      <h1>{{ shipmentId }}</h1>

      <p v-if="error" class="message">{{ error }}</p>
      <p v-else-if="loading || !detail" class="muted">Loading…</p>
      <template v-else>
        <source-path label="Reads" :path="detail.source" />
        <source-path label="Limits" :path="detail.thresholds_source" />

        <article v-for="(match, index) in detail.matches" :key="index" class="shipment-card">
          <dl class="fields">
            <div v-for="column in columns" :key="column">
              <dt>{{ column }}</dt>
              <dd>{{ match.row[column] }}</dd>
            </div>
          </dl>

          <source-path label="Logger" :path="match.logger.path" />

          <p v-if="!match.logger.found" class="message">
            Logger file not found: <code>{{ match.logger.path }}</code>
          </p>
          <p v-else-if="match.logger.readings.length === 0" class="message">
            This logger file has no readings.
          </p>
          <template v-else>
            <p v-if="!match.limits" class="muted">
              No limits for category "{{ match.row.product_category }}" in {{ detail.thresholds_source }}.
            </p>
            <logger-chart
              :readings="match.logger.readings"
              :limits="match.limits"
              :title="'Temperature readings for ' + match.row.shipment_id"
            />
          </template>
        </article>
      </template>
    </section>
  `,
}
