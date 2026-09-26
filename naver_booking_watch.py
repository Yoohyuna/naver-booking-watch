#!/usr/bin/env python3
"""네이버 예약 빈자리 감시 → 새로 빈 슬롯이 생기면 ntfy 알림."""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BUSINESS_ID = "1413691"
ITEM_ID = "6756172"
ITEM_NAME = "Escape Company"
DATE = "2026-10-03"

NTFY_TOPIC = os.environ["NTFY_TOPIC"]
STATE_FILE = Path(__file__).resolve().parent / "state.json"
KST = timezone(timedelta(hours=9))

BOOKING_URL = (
    f"https://m.booking.naver.com/booking/12/bizes/{BUSINESS_ID}"
    f"/items/{ITEM_ID}?startDate={DATE}"
)
QUERY = (
    "query schedule($scheduleParams: ScheduleParams) { schedule(input: $scheduleParams) "
    "{ bizItemSchedule { hourly { unitStartTime unitStock unitBookingCount "
    "isUnitSaleDay isUnitBusinessDay } } } }"
)


def fetch_open_slots():
    body = {
        "operationName": "schedule",
        "variables": {
            "scheduleParams": {
                "businessTypeId": 12,
                "businessId": BUSINESS_ID,
                "bizItemId": ITEM_ID,
                "startDateTime": f"{DATE}T00:00:00",
                "endDateTime": f"{DATE}T23:59:59",
                "fixedTime": True,
                "includesHolidaySchedules": True,
            }
        },
        "query": QUERY,
    }
    req = urllib.request.Request(
        "https://m.booking.naver.com/graphql?opName=schedule",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
            "Referer": BOOKING_URL,
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.load(resp)
    hourly = data["data"]["schedule"]["bizItemSchedule"]["hourly"]
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    return sorted(
        h["unitStartTime"][11:16]
        for h in hourly
        if h["isUnitSaleDay"] and h["isUnitBusinessDay"]
        and h["unitBookingCount"] < h["unitStock"]
        and h["unitStartTime"] > now
    )


def notify(message):
    body = {
        "topic": NTFY_TOPIC,
        "title": f"{ITEM_NAME} 빈자리!",
        "message": message,
        "priority": 5,
        "tags": ["rotating_light"],
        "click": BOOKING_URL,
    }
    req = urllib.request.Request(
        "https://ntfy.sh/",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=15)


def main():
    if datetime.now(KST).strftime("%Y-%m-%d") > DATE:
        print("감시 날짜가 지났습니다.")
        return

    try:
        prev = json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        prev = []

    open_slots = fetch_open_slots()
    print(f"{ITEM_NAME} {DATE} 빈자리: {open_slots or '없음'}")

    new_slots = sorted(set(open_slots) - set(prev))
    if new_slots:
        notify(f"{DATE} {', '.join(new_slots)} 빈자리 났어요. 탭해서 바로 예약하세요.")
        print(f"알림 전송: {new_slots}")

    STATE_FILE.write_text(json.dumps(open_slots) + "\n")


if __name__ == "__main__":
    sys.exit(main())
