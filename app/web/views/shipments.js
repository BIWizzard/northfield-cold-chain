import SourcePath from './source-path.js'

// The columns of data/reference/shipments.csv, in file order.
export const COLUMNS = ['shipment_id', 'ship_date', 'week', 'carrier_id', 'lane_id', 'product_category', 'logger_file']

// Columns shown in the monospace face: IDs, codes, and paths.
const MONO = ['shipment_id', 'week', 'carrier_id', 'lane_id', 'logger_file']

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// "2026-10-26" as "Oct 26".
function shortDate(date) {
  const [, month, day] = date.split('-').map(Number)
  return MONTHS[month - 1] + ' ' + day
}

export default {
  name: 'ShipmentsView',
  components: { SourcePath },
  props: {
    weeks: Array,
    weekDates: Object,
    week: String,
    source: String,
    shipments: Array,
    loading: Boolean,
    error: String,
  },
  data() {
    // The week strip's tab stop: the open week, until the arrow keys move it.
    return { columns: COLUMNS, focusWeek: null }
  },
  computed: {
    dates() {
      return this.weekDates[this.week]
    },
  },
  watch: {
    week() {
      this.focusWeek = null
    },
  },
  methods: {
    shortDate,
    weekNumber(week) {
      return week ? week.replace('week-', '') : ''
    },
    weekTitle(week) {
      const dates = this.weekDates[week]
      return dates ? week + ': ' + shortDate(dates.first_ship_date) + ' to ' + shortDate(dates.last_ship_date) : week
    },
    cellClass(column) {
      return { mono: MONO.includes(column), dim: column === 'logger_file' }
    },
    shipmentHref(row) {
      return '#/shipment/' + encodeURIComponent(row.shipment_id)
    },
    open(row) {
      location.hash = this.shipmentHref(row)
    },
    // The week strip is one tab stop. Arrow keys, Home, and End move along it; Enter opens a week.
    moveAlongWeeks(event) {
      const links = [...event.currentTarget.querySelectorAll('a')]
      let index = links.indexOf(document.activeElement)
      if (index < 0) return
      if (event.key === 'ArrowRight') index++
      else if (event.key === 'ArrowLeft') index--
      else if (event.key === 'Home') index = 0
      else if (event.key === 'End') index = links.length - 1
      else return
      event.preventDefault()
      index = Math.max(0, Math.min(links.length - 1, index))
      this.focusWeek = this.weeks[index]
      links[index].focus()
    },
  },
  template: `
    <div class="page-head">
      <div>
        <h1>Week {{ weekNumber(week) }}</h1>
        <p v-if="dates" class="sub">Shipped {{ dates.first_ship_date }} to {{ dates.last_ship_date }}</p>
      </div>
      <div class="week-meta">
        <span v-if="!loading && !error"><b>{{ shipments.length }}</b> rows</span>
        <span>Week <b>{{ weeks.indexOf(week) + 1 }}</b> of {{ weeks.length }}</span>
      </div>
    </div>

    <section class="panel" :aria-label="'Shipments for ' + week">
      <div class="sources"><source-path v-if="source" label="Reads" :path="source" /></div>

      <nav aria-label="Weeks">
        <ul class="weeks" :style="{ gridTemplateColumns: 'repeat(' + weeks.length + ', minmax(0, 1fr))' }" @keydown="moveAlongWeeks">
          <li v-for="item in weeks" :key="item">
            <a
              :href="'#/week/' + item"
              :aria-current="item === week ? 'page' : null"
              :tabindex="item === (focusWeek || week) ? 0 : -1"
              :aria-label="weekTitle(item)"
              :title="weekTitle(item)"
            >
              <span class="n">{{ weekNumber(item) }}</span>
              <span v-if="weekDates[item]" class="d">{{ shortDate(weekDates[item].first_ship_date) }}</span>
            </a>
          </li>
        </ul>
      </nav>

      <p v-if="error" class="message">{{ error }}</p>
      <p v-else-if="loading" class="message muted">Loading…</p>
      <template v-else>
        <div class="table-wrap">
          <table>
            <caption class="visually-hidden">Rows of shipments.csv for {{ week }}, in file order</caption>
            <thead>
              <tr>
                <th v-for="column in columns" :key="column" scope="col">{{ column }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in shipments" :key="index" class="clickable" @click="open(row)">
                <td v-for="column in columns" :key="column" :class="cellClass(column)">
                  <a v-if="column === 'shipment_id'" :href="shipmentHref(row)" @click.stop>{{ row[column] }}</a>
                  <template v-else>{{ row[column] }}</template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="table-foot">
          <span>Rows in file order</span>
          <span>Use <kbd>[</kbd> <kbd>]</kbd> to change week</span>
        </div>
      </template>
    </section>
  `,
}
