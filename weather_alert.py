import urllib.request #v2
import urllib.parse
import urllib.error
import json
import os
from datetime import date, timedelta

# ============================================================
#  ⚙️  請修改這裡的設定
# ============================================================

LATITUDE  = 25.0330
LONGITUDE = 121.5654
LOCATION_NAME = "台北"

TEMP_DIFF_THRESHOLD = 5    # 溫差超過幾度就提醒（°C）

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

# ============================================================

WEATHER_DESCRIPTIONS = {
    0:  "晴天", 1: "大致晴朗", 2: "部分多雲", 3: "陰天",
    45: "霧", 48: "霧淞",
    51: "毛毛雨（小）", 53: "毛毛雨（中）", 55: "毛毛雨（大）",
    61: "小雨", 63: "中雨", 65: "大雨",
    71: "小雪", 73: "中雪", 75: "大雪",
    80: "陣雨（小）", 81: "陣雨（中）", 82: "陣雨（大）",
    85: "陣雪", 86: "大陣雪",
    95: "雷陣雨", 96: "雷陣雨伴冰雹", 99: "強烈雷陣雨伴冰雹",
}

UMBRELLA_WEATHER_CODES = {61, 63, 65, 71, 73, 75, 80, 81, 82, 85, 86, 95, 96, 99}
SEVERE_WEATHER_CODES   = {82, 86, 95, 96, 99}


def fetch_weather():
    today     = date.today()
    yesterday = today - timedelta(days=1)

    daily_url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={LATITUDE}&longitude={LONGITUDE}"
        f"&daily=temperature_2m_max,temperature_2m_min,weathercode"
        f"&timezone=Asia%2FTaipei"
        f"&start_date={yesterday}&end_date={today}"
    )
    with urllib.request.urlopen(daily_url, timeout=10) as resp:
        daily_data = json.loads(resp.read())

    daily = daily_data["daily"]
    daily_result = {}
    for i, d in enumerate(daily["time"]):
        daily_result[d] = {
            "max_temp":     daily["temperature_2m_max"][i],
            "min_temp":     daily["temperature_2m_min"][i],
            "weather_code": daily["weathercode"][i],
        }

    hourly_url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={LATITUDE}&longitude={LONGITUDE}"
        f"&hourly=weathercode"
        f"&timezone=Asia%2FTaipei"
        f"&start_date={today}&end_date={today}"
    )
    with urllib.request.urlopen(hourly_url, timeout=10) as resp:
        hourly_data = json.loads(resp.read())

    today_hourly_codes = hourly_data["hourly"]["weathercode"]

    return daily_result[str(yesterday)], daily_result[str(today)], today_hourly_codes


def build_message(yesterday, today, today_hourly_codes):
    alerts, tips, warnings = [], [], []

    y_max, y_min = yesterday["max_temp"], yesterday["min_temp"]
    t_max, t_min = today["max_temp"],     today["min_temp"]
    t_code = today["weather_code"]
    y_code = yesterday["weather_code"]

    y_desc = WEATHER_DESCRIPTIONS.get(y_code, f"代碼 {y_code}")
    t_desc = WEATHER_DESCRIPTIONS.get(t_code, f"代碼 {t_code}")

    min_diff = y_min - t_min
    if min_diff >= TEMP_DIFF_THRESHOLD:
        alerts.append(f"🥶 早晨最低溫比昨天低 {min_diff:.0f}°C（{y_min:.0f}°C → {t_min:.0f}°C）")
        tips.append("多穿一件外套或加件毛衣")
    elif min_diff <= -TEMP_DIFF_THRESHOLD:
        alerts.append(f"🌡️ 今天氣溫比昨天高 {abs(min_diff):.0f}°C（{y_min:.0f}°C → {t_min:.0f}°C）")
        tips.append("可以穿薄一點，但備著一件薄外套")

    if t_min <= 10:
        warnings.append(f"🧣 今天最低溫只有 {t_min:.0f}°C，非常寒冷！")
        tips.append("帽子、圍巾、手套都建議帶上")
    elif t_max >= 36:
        warnings.append(f"☀️ 今天最高溫達 {t_max:.0f}°C，高溫注意防曬補水！")
        tips.append("多喝水，避免長時間在戶外曝曬")

    today_rain_codes   = [c for c in today_hourly_codes if c in UMBRELLA_WEATHER_CODES]
    today_severe_codes = [c for c in today_hourly_codes if c in SEVERE_WEATHER_CODES]

    if today_severe_codes:
        worst_code = max(today_severe_codes)
        alerts.append(f"⛈️ 今天有劇烈天氣：{WEATHER_DESCRIPTIONS.get(worst_code, '')}，請多加注意！")
        tips.append("盡量減少外出，外出務必帶傘")
    elif today_rain_codes:
        worst_code = max(today_rain_codes)
        alerts.append(f"🌧️ 今天某時段會下雨（{WEATHER_DESCRIPTIONS.get(worst_code, '')}）")
        tips.append("記得帶傘！")

    if not alerts and not warnings:
        return None

    lines = [f"## 🌤 {LOCATION_NAME}天氣提醒"]
    lines.append(f"昨天：{y_min:.0f}–{y_max:.0f}°C　{y_desc}")
    lines.append(f"今天：{t_min:.0f}–{t_max:.0f}°C　{t_desc}")
    lines.append("")
    for w in warnings:
        lines.append(w)
    for a in alerts:
        lines.append(a)
    if tips:
        lines.append("\n📋 **建議：**")
        for t in tips:
            lines.append(f"・{t}")

    return "\n".join(lines)


def send_discord(message):
    if not DISCORD_WEBHOOK_URL:
        print("⚠️  找不到 DISCORD_WEBHOOK_URL")
        return False

    # 印出 URL 前段，確認有讀到正確的值
    print(f"🔗 使用 Webhook URL: {DISCORD_WEBHOOK_URL[:50]}...")

    payload = json.dumps({"content": message}, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        DISCORD_WEBHOOK_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "weather-alert-bot/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            print(f"✅ Discord 回應狀態碼：{status}")
            return status in (200, 204)
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP 錯誤：{e.code} {e.reason}")
        print(f"❌ 回應內容：{e.read().decode('utf-8', errors='ignore')}")
        return False


def main():
    print("📡 正在取得天氣資料...")
    yesterday_data, today_data, today_hourly_codes = fetch_weather()
    print(f"昨天：{yesterday_data}")
    print(f"今天：{today_data}")
    print(f"今天逐小時天氣代碼：{today_hourly_codes}")

    message = build_message(yesterday_data, today_data, today_hourly_codes)

    if message is None:
        print("✅ 今天天氣正常，不需要提醒。")
        return

    print("📨 準備發送 Discord 通知...")
    print(message)

    success = send_discord(message)
    if not success:
        raise Exception("Discord 發送失敗，請查看上方錯誤訊息")


if __name__ == "__main__":
    main()
