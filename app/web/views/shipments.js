import SourcePath from './source-path.js'

// The columns of data/reference/shipments.csv, in file order.
export const COLUMNS = ['shipment_id', 'ship_date', 'week', 'carrier_id', 'lane_id', 'product_category', 'logger_file']

export default {
  name: 'ShipmentsView',
  components: { SourcePath },
  props: {
    weeks: Array,
    week: String,
    source: String,
    shipments: Array,
    loading: Boolean,
    error: String,
  },
  data() {
    return { columns: COLUMNS }
  },
  methods: {
    weekLabel(week) {
      return week ? week.replace('week-', 'Week ') : ''
    },
    shipmentHref(row) {
      return '#/shipment/' + encodeURIComponent(row.shipment_id)
    },
    open(row) {
      location.hash = this.shipmentHref(row)
    },
  },
  template: `
    <div class="shipments-layout">
      <nav class="week-list" aria-label="Weeks">
        <h2>Weeks</h2>
        <ul>
          <li v-for="item in weeks" :key="item">
            <a :href="'#/week/' + item" :aria-current="item === week ? 'page' : null">{{ weekLabel(item) }}</a>
          </li>
        </ul>
      </nav>

      <section class="panel">
        <h1>{{ weekLabel(week) || 'Shipments' }}</h1>
        <source-path v-if="source" label="Reads" :path="source" />

        <p v-if="error" class="message">{{ error }}</p>
        <p v-else-if="loading" class="muted">Loading…</p>
        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th v-for="column in columns" :key="column" scope="col">{{ column }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in shipments" :key="index" class="clickable" @click="open(row)">
                <td v-for="column in columns" :key="column">
                  <a v-if="column === 'shipment_id'" :href="shipmentHref(row)" @click.stop>{{ row[column] }}</a>
                  <template v-else>{{ row[column] }}</template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  `,
}
