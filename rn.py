"""Upstream provider clients for phone-number refresh.

All handlers take a 10-digit phone number string and return a unified code:
    0 = number not found at the provider
    1 = refreshed successfully
    2 = wait (recently refreshed / queued)
    4 = unknown / error
"""
import requests

from sky_app import Recaptcha3Pypass

NOT_FOUND = 0
REFRESHED = 1
WAIT = 2
ERROR = 4

REQUEST_TIMEOUT = 20  # seconds, applied to every upstream call


def layan(number: str) -> int:
    url = "https://api.layan-t.net/api/Subscribtions/CustomersRefreshNumber"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:149.0) Gecko/20100101 Firefox/149.0",
        "Accept": "*/*",
        "Content-Type": "application/json",
        "LANG": "ar",
        "Origin": "https://rn.layan-t.net",
        "Referer": "https://rn.layan-t.net/",
    }
    payload = {"number": number}

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
        text = r.text
        if "لم يتم العثور على رقمك" in text:
            return NOT_FOUND
        if "يمكنك تحديث الرقم مرة كل خمس ساعات" in text:
            return WAIT
        if "تم ارسال طلبك بنجاح" in text:
            return REFRESHED
        return ERROR
    except Exception:
        return ERROR


def aloha(phone_number: str) -> int:
    url = "https://refresh.telecom.co.il/home/refreshNumber"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://refresh.telecom.co.il",
        "Referer": "https://refresh.telecom.co.il/home",
    }
    data = {"phone_number": phone_number}

    try:
        r = requests.post(url, headers=headers, data=data, timeout=REQUEST_TIMEOUT)
        msg = r.json().get("message", "")
        if "Wrong Numbe" in msg:
            return NOT_FOUND
        if "number updated last 6 hours" in msg:
            return WAIT
        if "Phone number refreshed" in msg:
            return REFRESHED
        if "number waiting in queue" in msg:
            return WAIT
        return ERROR
    except Exception:
        return ERROR


def areen(number: str) -> int:
    url = "https://api.areen.net/api/common/RefreshMobileNumber"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Content-Type": "application/json",
        "HX-Current-URL": "https://update.areen.net/",
        "HX-Request": "true",
        "HX-Target": "result",
        "HX-Trigger": "mobileForm",
        "Origin": "https://update.areen.net",
        "Referer": "https://update.areen.net/",
    }
    payload = {"MobNumber": number}

    try:
        r = requests.post(url, headers=headers, data=payload, timeout=REQUEST_TIMEOUT)
        sc = r.json().get("StatusCode")
        if sc == 993:
            return WAIT
        if sc == 250:
            return NOT_FOUND
        if sc == 23:
            return REFRESHED
        return ERROR
    except Exception:
        return ERROR


def sky(number: str) -> int:
    anchor_url = (
        "https://www.google.com/recaptcha/api2/anchor"
        "?ar=1&k=6LcMCXYpAAAAABWt8J3o93Z0YRZgbFCd-OfBN5ov"
        "&co=aHR0cHM6Ly9ybi5za3ktNWcubmV0OjQ0Mw.."
        "&hl=en&v=gTpTIWhbKpxADzTzkcabhXN4"
        "&size=invisible&anchor-ms=20000&execute-ms=30000&cb=gyhpito0swjh"
    )
    reload_url = (
        "https://www.google.com/recaptcha/api2/reload"
        "?k=6LcMCXYpAAAAABWt8J3o93Z0YRZgbFCd-OfBN5ov"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://rn.sky-5g.net",
        "Referer": "https://rn.sky-5g.net/",
    }

    try:
        captcha_token = Recaptcha3Pypass(anchor_url, reload_url).response()
        data = {"captcha": captcha_token, "phoneNumber": number}
        r = requests.post(
            "https://rn.sky-5g.net/",
            headers=headers,
            data=data,
            timeout=REQUEST_TIMEOUT,
        )
        text = r.text
        if "الرقم غير موجود بالنظام" in text:
            return NOT_FOUND
        if "تم تحديث الرقم أعد تشغيل الجهاز خلال 10 دقاي" in text:
            return REFRESHED
        if "لقد قمت بتحديث الرقم قبل قليل الرجاء الانتظار قليلا" in text:
            return WAIT
        return ERROR
    except Exception:
        return ERROR
