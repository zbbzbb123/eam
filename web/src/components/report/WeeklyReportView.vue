<script setup>
import WeekSummaryCard from './WeekSummaryCard.vue'
import MacroCapitalSection from './MacroCapitalSection.vue'
import HoldingReviewCard from './HoldingReviewCard.vue'
import OpportunityCard from './OpportunityCard.vue'

const props = defineProps({ content: { type: Object, required: true } })
</script>

<template>
  <div class="weekly-report">
    <WeekSummaryCard :summary="content.week_summary" />

    <MacroCapitalSection v-if="content.macro_capital" :data="content.macro_capital" />

    <h2 class="section-title">持仓中长期点评</h2>
    <div class="holdings-list">
      <HoldingReviewCard
        v-for="h in content.holdings"
        :key="h.symbol"
        :holding="h"
        :is-weekly="true"
      />
    </div>

    <template v-if="content.opportunities?.length">
      <h2 class="section-title">新机会发掘</h2>
      <div class="opportunities-list">
        <OpportunityCard
          v-for="o in content.opportunities"
          :key="o.symbol"
          :opportunity="o"
        />
      </div>
    </template>

    <template v-if="content.risk_alerts?.length">
      <h2 class="section-title">风险提醒</h2>
      <div class="risk-alerts">
        <div v-for="(alert, i) in content.risk_alerts" :key="i" class="risk-alert-item">
          <span class="risk-level" :class="alert.level">{{ alert.level }}</span>
          <span class="risk-message">{{ alert.message }}</span>
        </div>
      </div>
    </template>

    <template v-if="content.next_week_events?.length">
      <h2 class="section-title">下周关注</h2>
      <div class="events-list">
        <div v-for="(e, i) in content.next_week_events" :key="i" class="event-item">
          <span class="event-date">{{ e.date }}</span>
          <span class="event-text">{{ e.event }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.weekly-report {
  max-width: 100%;
  overflow: hidden;
}
.section-title {
  font-size: 16px;
  color: var(--text);
  margin: 24px 0 12px;
  font-weight: 600;
}
.holdings-list, .opportunities-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.risk-alerts {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.risk-alert-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-left: 3px solid var(--red);
  border-radius: var(--radius);
}
.risk-level {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
  text-transform: uppercase;
}
.risk-level.high, .risk-level.critical {
  background: rgba(255,82,82,0.15);
  color: var(--red);
}
.risk-level.medium {
  background: rgba(255,152,0,0.15);
  color: var(--orange);
}
.risk-level.low {
  background: rgba(68,138,255,0.15);
  color: var(--blue);
}
.risk-message {
  font-size: 13px;
  color: var(--text);
}
.events-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.event-item {
  display: flex;
  gap: 12px;
  padding: 8px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 13px;
}
.event-date {
  color: var(--text-muted);
  font-family: monospace;
  flex-shrink: 0;
}
.event-text {
  color: var(--text);
}
</style>
