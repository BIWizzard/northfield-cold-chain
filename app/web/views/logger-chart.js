// Logger readings as an SVG line chart, with the category's limits as a shaded band and lines.
// Point at the chart, or focus it and use the arrow keys, to read single readings.
import { shortDate } from './dates.js'

const WIDTH = 960
const HEIGHT = 262
const MARGIN = { top: 12, right: 104, bottom: 42, left: 48 }
const HOUR_MS = 60 * 60 * 1000

// "2026-08-15 15:15", in UTC.
function formatTime(time) {
  return new Date(time).toISOString().slice(0, 16).replace('T', ' ')
}

export default {
  name: 'LoggerChart',
  props: {
    readings: { type: Array, required: true },
    limits: Object,
    category: String,
    title: String,
  },
  data() {
    // cursor is the index of the reading shown in the readout, or null when none is.
    return { width: WIDTH, height: HEIGHT, margin: MARGIN, cursor: null }
  },
  computed: {
    viewBox() {
      return '0 0 ' + WIDTH + ' ' + HEIGHT
    },
    plotWidth() {
      return WIDTH - MARGIN.left - MARGIN.right
    },
    plotHeight() {
      return HEIGHT - MARGIN.top - MARGIN.bottom
    },
    times() {
      return this.readings.map((reading) => Date.parse(reading.timestamp))
    },
    temps() {
      return this.readings.map((reading) => reading.temp_c)
    },
    timeRange() {
      return { start: this.times[0], end: this.times[this.times.length - 1] }
    },
    // The temperature axis covers every reading and every limit, plus 1 °C of room.
    tempRange() {
      const values = [...this.temps]
      if (this.limits) {
        for (const value of [this.limits.min_c, this.limits.max_c]) {
          if (value !== null) values.push(value)
        }
      }
      return {
        low: Math.floor(Math.min(...values) - 1),
        high: Math.ceil(Math.max(...values) + 1),
      }
    },
    points() {
      return this.times.map((time, i) => this.x(time) + ',' + this.y(this.temps[i])).join(' ')
    },
    tempTicks() {
      const { low, high } = this.tempRange
      const step = [0.5, 1, 2, 5, 10].find((size) => (high - low) / size <= 7) || 20
      const ticks = []
      for (let i = Math.ceil(low / step); i * step <= high; i++) {
        const value = i * step
        ticks.push({ value, y: this.y(value), label: Number.isInteger(step) ? String(value) : value.toFixed(1) })
      }
      return ticks
    },
    // Hour ticks along the bottom, with the date under the first tick of each day.
    timeTicks() {
      const { start, end } = this.timeRange
      const hours = [1, 2, 3, 6, 12, 24].find((size) => (end - start) / (size * HOUR_MS) <= 10) || 48
      const step = hours * HOUR_MS
      const ticks = []
      let lastDay = null
      for (let time = Math.ceil(start / step) * step; time <= end; time += step) {
        const iso = new Date(time).toISOString()
        const day = iso.slice(0, 10)
        ticks.push({
          time,
          x: this.x(time),
          label: iso.slice(11, 16),
          day: day === lastDay ? null : shortDate(day),
        })
        lastDay = day
      }
      return ticks
    },
    band() {
      if (!this.limits) return null
      const top = this.y(this.limits.max_c ?? this.tempRange.high)
      const bottom = this.y(this.limits.min_c ?? this.tempRange.low)
      return { y: top, height: bottom - top }
    },
    limitLines() {
      if (!this.limits) return []
      return [
        { name: 'max', value: this.limits.max_c },
        { name: 'min', value: this.limits.min_c },
      ].map((line) => ({
        name: line.name,
        y: this.y(line.value),
        label: line.name + ' ' + line.value.toFixed(1) + ' °C',
      }))
    },
    caption() {
      return (
        this.readings.length + ' readings, ' +
        formatTime(this.timeRange.start) + ' to ' + formatTime(this.timeRange.end) + ' UTC. Temperatures in °C.'
      )
    },
    // The reading under the pointer or the keyboard cursor.
    current() {
      if (this.cursor === null) return null
      return {
        x: this.x(this.times[this.cursor]),
        y: this.y(this.temps[this.cursor]),
        time: formatTime(this.times[this.cursor]),
        temp: this.temps[this.cursor].toFixed(1),
      }
    },
  },
  methods: {
    x(time) {
      const span = Math.max(this.timeRange.end - this.timeRange.start, 1)
      return MARGIN.left + ((time - this.timeRange.start) / span) * this.plotWidth
    },
    y(temp) {
      const { low, high } = this.tempRange
      return MARGIN.top + ((high - temp) / (high - low)) * this.plotHeight
    },
    show(index) {
      this.cursor = Math.max(0, Math.min(this.readings.length - 1, index))
    },
    // Show the reading nearest in time to the pointer.
    pointAt(event) {
      const svg = this.$refs.svg
      const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(svg.getScreenCTM().inverse())
      const span = this.timeRange.end - this.timeRange.start
      const time = this.timeRange.start + ((point.x - MARGIN.left) / this.plotWidth) * span
      let nearest = 0
      this.times.forEach((each, i) => {
        if (Math.abs(each - time) < Math.abs(this.times[nearest] - time)) nearest = i
      })
      this.show(nearest)
    },
    leave() {
      if (document.activeElement !== this.$refs.svg) this.cursor = null
    },
    // Arrow keys step one reading, or four with Shift; Home and End jump to the ends.
    step(event) {
      const last = this.readings.length - 1
      const size = event.shiftKey ? 4 : 1
      if (event.key === 'ArrowRight') this.show(this.cursor === null ? 0 : this.cursor + size)
      else if (event.key === 'ArrowLeft') this.show(this.cursor === null ? last : this.cursor - size)
      else if (event.key === 'Home') this.show(0)
      else if (event.key === 'End') this.show(last)
      else return
      event.preventDefault()
    },
  },
  template: `
    <div class="panel-head chart-head">
      <div class="chart-title">
        <h2>Logger readings</h2>
        <span class="readout" aria-live="polite">
          <template v-if="current">
            <span>{{ current.time }} UTC</span>
            <span>{{ current.temp }} °C</span>
            <span class="muted">reading {{ cursor + 1 }} of {{ readings.length }}</span>
          </template>
          <span v-else class="muted">Point at the chart, or focus it and use the arrow keys</span>
        </span>
      </div>
      <div class="legend" aria-hidden="true">
        <span><i class="swatch-line"></i>temp_c</span>
        <template v-if="limits">
          <span><i class="swatch-band"></i>{{ category }} range</span>
          <span><i class="swatch-limit"></i>limits</span>
        </template>
      </div>
    </div>
    <figure class="chart">
      <svg
        ref="svg"
        :viewBox="viewBox"
        role="img"
        tabindex="0"
        :aria-label="title + '. Use the left and right arrow keys to step through the readings.'"
        @pointermove="pointAt"
        @pointerleave="leave"
        @blur="cursor = null"
        @keydown="step"
      >
        <rect v-if="band" class="chart-band" :x="margin.left" :y="band.y" :width="plotWidth" :height="band.height" />

        <g v-for="tick in tempTicks" :key="'temp' + tick.value" class="chart-grid">
          <line :x1="margin.left" :x2="width - margin.right" :y1="tick.y" :y2="tick.y" />
          <text class="tick-label" text-anchor="end" :x="margin.left - 8" :y="tick.y" dy="0.32em">{{ tick.label }}</text>
        </g>

        <line class="chart-axis" :x1="margin.left" :x2="width - margin.right" :y1="height - margin.bottom" :y2="height - margin.bottom" />
        <g v-for="tick in timeTicks" :key="'time' + tick.time">
          <line class="chart-axis" :x1="tick.x" :x2="tick.x" :y1="height - margin.bottom" :y2="height - margin.bottom + 4" />
          <text class="tick-label" text-anchor="middle" :x="tick.x" :y="height - margin.bottom + 17">{{ tick.label }}</text>
          <text v-if="tick.day" class="day-label" text-anchor="middle" :x="tick.x" :y="height - margin.bottom + 33">{{ tick.day }}</text>
        </g>

        <g v-for="line in limitLines" :key="line.name" class="chart-limit">
          <line :x1="margin.left" :x2="width - margin.right" :y1="line.y" :y2="line.y" />
          <text :x="width - margin.right + 8" :y="line.y" dy="0.32em">{{ line.label }}</text>
        </g>

        <polyline class="chart-line" :points="points" />

        <g v-if="current" class="cursor">
          <line :x1="current.x" :x2="current.x" :y1="margin.top" :y2="height - margin.bottom" />
          <circle :cx="current.x" :cy="current.y" r="4" />
        </g>
      </svg>
      <figcaption>{{ caption }}</figcaption>
    </figure>
  `,
}
