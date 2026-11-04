import CopyButton from './copy-button.js'

// The start page: what the data covers and which repo files the app reads.
// Only counts of records and date ranges: nothing here looks at any one shipment.
export default {
  name: 'HomeView',
  components: { CopyButton },
  props: {
    overview: Object,
    loading: Boolean,
    error: String,
    shipmentsHref: String,
  },
  computed: {
    latest() {
      return this.overview && this.overview.latest_week
    },
    firstWeek() {
      return this.overview && this.overview.weeks.length ? this.overview.weeks[0].week : ''
    },
    // The repo's data folder as a tree. Each file row has a Copy button for its exact path.
    files() {
      const data = this.overview
      const name = (path) => path.split('/').pop()
      return [
        { branch: '', name: 'northfield-cold-chain/' },
        { branch: '└─ ', name: 'data/' },
        { branch: '   ├─ ', name: 'reference/' },
        { branch: '   │  ├─ ', name: name(data.source), path: data.source, meta: data.shipment_rows + ' rows' },
        { branch: '   │  ├─ ', name: name(data.carriers_source), path: data.carriers_source, meta: data.carriers + ' rows' },
        { branch: '   │  └─ ', name: name(data.lanes_source), path: data.lanes_source, meta: data.lanes + ' rows' },
        { branch: '   ├─ ', name: 'sop/' },
        {
          branch: '   │  └─ ', name: name(data.thresholds_source), path: data.thresholds_source,
          meta: data.categories.length + ' categories',
        },
        { branch: '   └─ ', name: 'raw/loggers/' },
        {
          branch: '      └─ ', name: this.latest ? this.firstWeek + ' … ' + this.latest.week + '/' : 'week folders',
          path: data.loggers_source, meta: 'Logger CSVs',
        },
      ]
    },
  },
  template: `
    <div class="home-grid">
      <div class="home-intro">
        <h1>Cold-Chain Exception Desk</h1>
        <p>
          Northfield Provisions ships fresh, frozen, and marinated product from its plants to its distribution
          centers, each load with a temperature logger. This desk shows the shipment records and logger readings
          as they sit in the repo, so you can look at the same files Claude Code reads.
        </p>
        <div class="actions">
          <a class="btn" :href="shipmentsHref">Browse shipments <kbd>g s</kbd></a>
          <a class="btn secondary" href="#/reference">Open reference <kbd>g r</kbd></a>
        </div>
      </div>
      <section v-if="latest" class="panel" aria-labelledby="latest-title">
        <div class="panel-head"><h2 id="latest-title">Latest week</h2></div>
        <div class="latest">
          <div>
            <div class="latest-week">{{ latest.week }}</div>
            <p>Shipped {{ latest.first_ship_date }} to {{ latest.last_ship_date }}</p>
            <p>{{ latest.rows }} rows</p>
          </div>
          <a class="btn" :href="'#/week/' + latest.week">Open {{ latest.week }}</a>
        </div>
      </section>
    </div>

    <div v-if="error" class="panel"><p class="message">{{ error }}</p></div>
    <p v-else-if="loading || !overview" class="muted">Loading…</p>
    <div v-else class="home-grid">
      <section class="panel" aria-labelledby="data-title">
        <div class="panel-head"><h2 id="data-title">What the data covers</h2></div>
        <dl class="facts">
          <dt>Weeks</dt>
          <dd>{{ overview.weeks.length }}<small v-if="latest">{{ firstWeek }} to {{ latest.week }}</small></dd>
          <dt>Ship dates</dt>
          <dd>{{ overview.first_ship_date }} to {{ overview.last_ship_date }}</dd>
          <dt>Shipment rows</dt>
          <dd>{{ overview.shipment_rows }}<small>in shipments.csv</small></dd>
          <dt>Carriers</dt>
          <dd>{{ overview.carriers }}</dd>
          <dt>Lanes</dt>
          <dd>{{ overview.lanes }}<small>from {{ overview.plants }} plants to {{ overview.distribution_centers }} distribution centers</small></dd>
          <dt>Product categories</dt>
          <dd>{{ overview.categories.length }}<small>{{ overview.categories.join(', ') }}</small></dd>
          <dt>Logger readings</dt>
          <dd>Every {{ overview.reading_interval_minutes }} minutes<small>timestamps in UTC, temperatures in °C</small></dd>
        </dl>
      </section>
      <section class="panel" aria-labelledby="files-title">
        <div class="panel-head"><h2 id="files-title">Files this app reads</h2></div>
        <ul class="tree">
          <li v-for="file in files" :key="file.branch + file.name">
            <span><span class="branch" aria-hidden="true">{{ file.branch }}</span><span :class="file.path ? 'name' : 'dir'">{{ file.name }}</span></span>
            <span class="meta">{{ file.meta }}</span>
            <copy-button v-if="file.path" :path="file.path" />
            <span v-else class="spacer"></span>
          </li>
        </ul>
      </section>
    </div>
  `,
}
