import httpx
import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict

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
        取得最近 7 天的流量統計數據（Free 方案相容）
        使用 httpRequests1dGroups（所有方案皆可用）
        """
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

        query = """
        query GetTrafficData($zoneTag: string!, $start: Date!, $end: Date!) {
          viewer {
            zones(filter: { zoneTag: $zoneTag }) {
              httpRequests1dGroups(
                limit: 50
                filter: { date_geq: $start, date_leq: $end }
                orderBy: [date_ASC]
              ) {
                dimensions { date clientCountryName }
                sum { requests pageViews }
                uniq { uniques }
              }
            }
          }
        }
        """

        variables = {
            "zoneTag": self.zone_id,
            "start": start_date,
            "end": end_date,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.url,
                    headers=self.headers,
                    json={"query": query, "variables": variables}
                )
                res_data = response.json()

                if res_data.get("errors"):
                    logger.error(f"Cloudflare API Error: {res_data['errors']}")
                    return None

                zones = res_data.get("data", {}).get("viewer", {}).get("zones", [])
                if not zones:
                    return None

                rows = zones[0].get("httpRequests1dGroups", [])

                # 聚合每日統計
                daily_map = defaultdict(lambda: {"visits": 0, "pageviews": 0, "requests": 0})
                country_map = defaultdict(int)

                for row in rows:
                    date = row["dimensions"]["date"]
                    country = row["dimensions"].get("clientCountryName") or "Unknown"
                    requests = row["sum"].get("requests", 0)
                    pageviews = row["sum"].get("pageViews", 0)
                    uniques = row.get("uniq", {}).get("uniques", 0)

                    daily_map[date]["visits"] += uniques
                    daily_map[date]["pageviews"] += pageviews
                    daily_map[date]["requests"] += requests

                    country_map[country] += requests

                daily = [
                    {"date": k, **v}
                    for k, v in sorted(daily_map.items())
                ]

                top_countries = sorted(
                    [{"country": k, "views": v} for k, v in country_map.items()],
                    key=lambda x: x["views"], reverse=True
                )[:10]

                return {
                    "daily": daily,
                    "topPages": [],       # Free 方案無法取得路徑分析
                    "topCountries": top_countries,
                    "topReferrers": [],   # Free 方案無法取得來源分析
                }
        except Exception as e:
            logger.error(f"Failed to fetch Cloudflare data: {e}")
            return None
