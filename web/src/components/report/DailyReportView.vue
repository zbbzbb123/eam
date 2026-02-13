<script setup>
import PortfolioSummaryCard from './PortfolioSummaryCard.vue'
import HoldingReviewCard from './HoldingReviewCard.vue'
import OpportunityCard from './OpportunityCard.vue'

const props = defineProps({ content: { type: Object, required: true } })
</script>

<template>
  <div class="daily-report">
    <PortfolioSummaryCard :summary="content.portfolio_summary" />

    <h2 class="section-title">持仓点评</h2>
    <div class="holdings-list">
      <HoldingReviewCard
        v-for="h in content.holdings"
        :key="h.symbol"
        :holding="h"
      />
    </div>

    <template v-if="content.opportunities?.length">
      <h2 class="section-title">机会雷达</h2>
      <div class="opportunities-list">
        <OpportunityCard
          v-for="o in content.opportunities"
          :key="o.symbol"
          :opportunity="o"
        />
      </div>
    </template>
  </div>
</template>

<style scoped>
.daily-report {
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
</style>
