import httpx
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

class CloudflareAnalyticsService:
    def __init__(self, api_token: str, account_id: str, zone_id: str):
        self.api_token = api_token
        self.account_id = account_id
        self.zone_id = zone_id
        self.url = "https://api.cloudflare.com/client/v4/graphql"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    async def get_traffic_stats(self):
        """
        取得最近 7 天的流量統計數據
        包括：造訪次數、熱門頁面、來源、國家
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=7)
        
        # GraphQL 查詢
        query = """
        query GetTrafficData($zoneTag: string, $filter: ZoneHttpRequestsAdaptiveGroupsFilter_InputObject) {
          viewer {
            zones(filter: { zoneTag: $zoneTag }) {
              # 每日造訪與頁面瀏覽
              dailyStats: httpRequestsAdaptiveGroups(
                limit: 100
                filter: $filter
                orderBy: [date_ASC]
              ) {
                dimensions { date }
                sum { pageViews, visits }
              }
              # 熱門頁面 (以路徑分組)
              topPages: httpRequestsAdaptiveGroups(
                limit: 10
                filter: $filter
                orderBy: [sum_pageViews_DESC]
              ) {
                dimensions { clientRequestPath }
                sum { pageViews }
              }
              # 訪客國家
              topCountries: httpRequestsAdaptiveGroups(
                limit: 10
                filter: $filter
                orderBy: [sum_pageViews_DESC]
              ) {
                dimensions { clientCountryName }
                sum { pageViews }
              }
              # 來源網站
              topReferrers: httpRequestsAdaptiveGroups(
                limit: 10
                filter: $filter
                orderBy: [sum_pageViews_DESC]
              ) {
                dimensions { clientRefererHost }
                sum { pageViews }
              }
            }
          }
        }
        """
        
        variables = {
            "zoneTag": self.zone_id,
            "filter": {
                "datetime_geq": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "datetime_leq": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.url,
                    headers=self.headers,
                    json={"query": query, "variables": variables}
                )
                res_data = response.json()
                
                if "errors" in res_data and res_data["errors"]:
                    logger.error(f"Cloudflare API Error: {res_data['errors']}")
                    return None
                
                data = res_data.get("data", {}).get("viewer", {}).get("zones", [{}])[0]
                return {
                    "daily": [
                        {"date": d["dimensions"]["date"], "visits": d["sum"]["visits"], "pageviews": d["sum"]["pageViews"]}
                        for d in data.get("dailyStats", [])
                    ],
                    "topPages": [
                        {"path": p["dimensions"]["clientRequestPath"], "views": p["sum"]["pageViews"]}
                        for p in data.get("topPages", [])
                    ],
                    "topCountries": [
                        {"country": c["dimensions"]["clientCountryName"], "views": c["sum"]["pageViews"]}
                        for c in data.get("topCountries", [])
                    ],
                    "topReferrers": [
                        {"host": r["dimensions"]["clientRefererHost"] or "Direct", "views": r["sum"]["pageViews"]}
                        for r in data.get("topReferrers", [])
                    ]
                }
        except Exception as e:
            logger.error(f"Failed to fetch Cloudflare data: {e}")
            return None
