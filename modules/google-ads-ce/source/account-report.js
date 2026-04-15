// Account health report — logs account status, billing info, and recent performance.
// Run this first to verify Scripts work on your account.

function main() {
  // Account info
  var account = AdsApp.currentAccount();
  Logger.log("=== ACCOUNT INFO ===");
  Logger.log("Name: " + account.getName());
  Logger.log("Customer ID: " + account.getCustomerId());
  Logger.log("Currency: " + account.getCurrencyCode());
  Logger.log("Timezone: " + account.getTimeZone());

  // Campaign summary
  var campaigns = AdsApp.campaigns().get();
  Logger.log("\n=== CAMPAIGNS (" + campaigns.totalNumEntities() + ") ===");
  while (campaigns.hasNext()) {
    var campaign = campaigns.next();
    Logger.log(
      "[" + campaign.getStatus() + "] " + campaign.getName() +
      " | Budget: " + campaign.getBudget().getAmount() + "/day" +
      " | Type: " + campaign.getAdvertisingChannelType()
    );
  }

  // Last 7 days performance
  var stats = account.getStatsFor("LAST_7_DAYS");
  Logger.log("\n=== LAST 7 DAYS ===");
  Logger.log("Impressions: " + stats.getImpressions());
  Logger.log("Clicks: " + stats.getClicks());
  Logger.log("Cost: " + stats.getCost());
  Logger.log("CTR: " + (stats.getCtr() * 100).toFixed(2) + "%");
  Logger.log("Avg CPC: " + stats.getAverageCpc());
  Logger.log("Conversions: " + stats.getConversions());

  Logger.log("\n=== DONE ===");
  Logger.log("Account is working. Scripts have full access.");
}
