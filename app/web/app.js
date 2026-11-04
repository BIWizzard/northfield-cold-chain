import { createApp, reactive } from './vendor/vue.esm-browser.prod.js'
import ShipmentsView from './views/shipments.js'
import ShipmentDetailView from './views/shipment-detail.js'

// Everything the views show lives here. The views only display it.
const state = reactive({
  weeks: [],
  week: null,
  source: null,
  shipments: [],
  shipmentId: null,
  detail: null,
  loading: false,
  error: null,
})

async function getJSON(url) {
  const response = await fetch(url)
  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.error || response.statusText)
  }
  return data
}

// Each navigation starts a new request. A reply to an older request is ignored,
// so a slow response can't overwrite the page the participant has moved on to.
let latestRequest = 0

async function loadWeek(week) {
  const request = ++latestRequest
  state.loading = true
  state.error = null
  state.shipments = []
  try {
    const data = await getJSON('/api/shipments?week=' + encodeURIComponent(week))
    if (request === latestRequest) {
      state.source = data.source
      state.shipments = data.shipments
    }
  } catch (error) {
    if (request === latestRequest) state.error = error.message
  } finally {
    if (request === latestRequest) state.loading = false
  }
}

async function loadShipment(shipmentId) {
  const request = ++latestRequest
  state.loading = true
  state.error = null
  state.detail = null
  try {
    const data = await getJSON('/api/shipments/' + encodeURIComponent(shipmentId))
    if (request === latestRequest) state.detail = data
  } catch (error) {
    if (request === latestRequest) state.error = error.message
  } finally {
    if (request === latestRequest) state.loading = false
  }
}

// Routes: #/week/week-13 shows a week, #/shipment/SHP-0142 shows one shipment.
function showRoute() {
  const [view, value] = location.hash.replace(/^#\/?/, '').split('/')
  state.shipmentId = view === 'shipment' && value ? decodeURIComponent(value) : null
  state.week = view === 'week' && state.weeks.includes(value) ? value : state.weeks[0]

  if (state.shipmentId) {
    loadShipment(state.shipmentId)
  } else {
    loadWeek(state.week)
  }
}

const App = {
  name: 'App',
  components: { ShipmentsView, ShipmentDetailView },
  data() {
    return { state }
  },
  template: `
    <shipment-detail-view
      v-if="state.shipmentId"
      :shipment-id="state.shipmentId"
      :detail="state.detail"
      :loading="state.loading"
      :error="state.error"
      :back-href="'#/week/' + state.week"
    />
    <shipments-view
      v-else
      :weeks="state.weeks"
      :week="state.week"
      :source="state.source"
      :shipments="state.shipments"
      :loading="state.loading"
      :error="state.error"
    />
  `,
}

function logRender() {
  console.log('render', this.$options.name, JSON.parse(JSON.stringify({ ...this.$props, ...this.$data })))
}

const app = createApp(App)
app.mixin({ mounted: logRender, updated: logRender })
// Report errors from components the same way the browser reports any uncaught error.
app.config.errorHandler = (error) => reportError(error)
app.mount('#app')

async function start() {
  try {
    const data = await getJSON('/api/weeks')
    state.weeks = data.weeks
    state.source = data.source
  } catch (error) {
    // fetch rejects with a TypeError only when the server can't be reached at all.
    const problem = error instanceof TypeError ? 'Could not reach the app server: ' : 'Could not load the weeks: '
    state.error = problem + error.message
    return
  }
  window.addEventListener('hashchange', showRoute)
  showRoute()
}

start()
