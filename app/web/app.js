// Adding a section: write its view in views/, import it below, and add one entry to SECTIONS.
// The entry gives the rail label, an optional `g` shortcut key and icon, and its routes: the
// first part of the hash (#/tools is the 'tools' route), the view to show, and the API URL it
// reads. The rail, breadcrumb, shortcuts list, and loading all follow from the entry.
import { createApp, nextTick, reactive } from './vendor/vue.esm-browser.prod.js'
import AppShell from './views/app-shell.js'
import ShortcutsDialog from './views/shortcuts-dialog.js'
import HomeView from './views/home.js'
import ShipmentsView from './views/shipments.js'
import ShipmentDetailView from './views/shipment-detail.js'
import ReferenceView from './views/reference.js'

// Everything the views show lives here. The views only display it.
const state = reactive({
  weeks: [],
  weekDates: {},
  week: null,
  source: null,
  shipmentId: null,
  route: null,
  data: null,
  loading: false,
  error: null,
  shortcutsOpen: false,
})

const SECTIONS = [
  {
    label: 'Home',
    key: 'h',
    icon: 'M2.5 8 9 2.75 15.5 8v7.25h-4.25v-4.5h-4.5v4.5H2.5z',
    href: () => '#/',
    routes: {
      '': {
        view: HomeView,
        api: () => '/api/overview',
        props: () => ({
          overview: state.data, loading: state.loading, error: state.error, shipmentsHref: '#/week/' + state.week,
        }),
      },
    },
  },
  {
    label: 'Shipments',
    key: 's',
    icon: 'M3.25 3h11.5a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H3.25a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM2.25 7h13.5M2.25 11h13.5M7 7v8',
    href: () => '#/week/' + state.week,
    routes: {
      week: {
        view: ShipmentsView,
        api: () => '/api/shipments?week=' + encodeURIComponent(state.week),
        props: () => ({
          weeks: state.weeks,
          weekDates: state.weekDates,
          week: state.week,
          source: state.source,
          shipments: state.data ? state.data.shipments : [],
          loading: state.loading,
          error: state.error,
        }),
        crumbs: () => [{ label: 'Shipments', href: '#/week/' + state.week }, { label: state.week }],
        keys: { '[': () => showWeek(-1), ']': () => showWeek(1) },
      },
      shipment: {
        view: ShipmentDetailView,
        api: () => '/api/shipments/' + encodeURIComponent(state.shipmentId),
        props: () => ({
          shipmentId: state.shipmentId,
          detail: state.data,
          loading: state.loading,
          error: state.error,
          backHref: '#/week/' + state.week,
        }),
        crumbs: () => [{ label: 'Shipments', href: '#/week/' + state.week }, { label: state.shipmentId }],
      },
    },
  },
  {
    label: 'Reference',
    key: 'r',
    icon: 'M3 3.25h4.5a1.5 1.5 0 0 1 1.5 1.5v10a1.25 1.25 0 0 0-1.25-1.25H3zM15 3.25h-4.5A1.5 1.5 0 0 0 9 4.75v10a1.25 1.25 0 0 1 1.25-1.25H15z',
    href: () => '#/reference',
    routes: {
      reference: {
        view: ReferenceView,
        api: () => '/api/reference',
        props: () => ({ reference: state.data, loading: state.loading, error: state.error }),
      },
    },
  },
]

// Every route by name, with the section it belongs to. A route without `props` gets the API
// response as `data`, and without `crumbs` shows its section's label.
const ROUTES = new Map(
  SECTIONS.flatMap((section) =>
    Object.entries(section.routes).map(([name, route]) => [name, { ...route, name, section }]),
  ),
)

// Keys shown in the shortcuts list besides each section's `g` key.
const SHORTCUTS = [
  { keys: ['[', ']'], action: 'Previous or next week' },
  { keys: ['←', '→'], action: 'Move along the week strip or the chart' },
  { keys: ['?'], action: 'Show this list' },
]

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

async function loadRoute(route) {
  const request = ++latestRequest
  state.data = null
  state.error = null
  state.loading = Boolean(route.api)
  if (!route.api) return
  try {
    const data = await getJSON(route.api())
    if (request === latestRequest) state.data = data
  } catch (error) {
    if (request === latestRequest) state.error = error.message
  } finally {
    if (request === latestRequest) state.loading = false
  }
}

// Routes: #/ is Home, #/week/week-13 shows a week, #/shipment/<shipment_id> shows one shipment,
// and #/reference shows the reference files. Anything else shows Home.
function showRoute() {
  const [view, value] = location.hash.replace(/^#\/?/, '').split('/')
  state.shipmentId = view === 'shipment' && value ? decodeURIComponent(value) : null
  state.week = view === 'week' && state.weeks.includes(value) ? value : state.weeks[0]

  state.route = ROUTES.has(view) && (view !== 'shipment' || state.shipmentId) ? view : ''
  loadRoute(ROUTES.get(state.route))
}

function showWeek(offset) {
  const next = state.weeks[state.weeks.indexOf(state.week) + offset]
  if (next) location.hash = '#/week/' + next
}

// After a page change, start at the top. If the link that was clicked has gone,
// move focus to the page so Tab carries on from there.
function afterRouteChange() {
  nextTick(() => {
    const main = document.getElementById('main')
    if (!main) return
    main.scrollTop = 0
    if (!document.activeElement || document.activeElement === document.body) main.focus({ preventScroll: true })
  })
}

// Keyboard shortcuts. None of them fire while typing in a field or with a modifier key held,
// and the browser's own keys, such as Backspace and the arrows, are left alone.
let pendingG = 0

function onKeydown(event) {
  if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey || state.shortcutsOpen) return
  const target = event.target
  if (target.isContentEditable || (target.closest && target.closest('input, textarea, select'))) return

  if (pendingG && Date.now() - pendingG < 1200) {
    pendingG = 0
    const section = SECTIONS.find((item) => item.key === event.key)
    if (section) {
      event.preventDefault()
      location.hash = section.href()
    }
    return
  }
  pendingG = 0
  if (event.key === 'g') {
    pendingG = Date.now()
  } else if (event.key === '?') {
    event.preventDefault()
    state.shortcutsOpen = true
  } else {
    const action = state.route !== null && ROUTES.get(state.route).keys?.[event.key]
    if (action) {
      event.preventDefault()
      action()
    }
  }
}

const App = {
  name: 'App',
  components: { AppShell, ShortcutsDialog },
  data() {
    return { state }
  },
  computed: {
    host() {
      return location.host
    },
    route() {
      return state.route === null ? null : ROUTES.get(state.route)
    },
    viewProps() {
      const route = this.route
      return route.props ? route.props() : { data: state.data, loading: state.loading, error: state.error }
    },
    nav() {
      return SECTIONS.map((section) => ({
        label: section.label,
        key: section.key || null,
        icon: section.icon || null,
        href: section.href(),
        current: Boolean(this.route) && this.route.section === section,
      }))
    },
    crumbs() {
      const route = this.route
      if (!route) return []
      return route.crumbs ? route.crumbs() : [{ label: route.section.label }]
    },
    shortcuts() {
      const sections = SECTIONS.filter((section) => section.key)
        .map((section) => ({ keys: ['g', section.key], action: section.label }))
      return [...sections, ...SHORTCUTS]
    },
  },
  watch: {
    crumbs: {
      handler(crumbs) {
        document.title = crumbs.map((crumb) => crumb.label).reverse().concat('Northfield Exception Desk').join(' | ')
      },
      immediate: true,
    },
  },
  template: `
    <app-shell :nav="nav" :crumbs="crumbs" :host="host" @show-shortcuts="state.shortcutsOpen = true">
      <component v-if="route" :is="route.view" v-bind="viewProps" />
      <div v-else-if="state.error" class="panel"><p class="message">{{ state.error }}</p></div>
    </app-shell>
    <shortcuts-dialog :open="state.shortcutsOpen" :shortcuts="shortcuts" @close="state.shortcutsOpen = false" />
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
    const data = await getJSON('/api/overview')
    state.weeks = data.weeks.map((entry) => entry.week)
    state.weekDates = Object.fromEntries(data.weeks.map(({ week, first_ship_date, last_ship_date }) => (
      [week, { first_ship_date, last_ship_date }]
    )))
    state.source = data.source
  } catch (error) {
    // fetch rejects with a TypeError only when the server can't be reached at all.
    const problem = error instanceof TypeError ? 'Could not reach the app server: ' : 'Could not load the weeks: '
    state.error = problem + error.message
    return
  }
  window.addEventListener('hashchange', () => {
    showRoute()
    afterRouteChange()
  })
  window.addEventListener('keydown', onKeydown)
  showRoute()
}

start()
