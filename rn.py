import requests

# 0 is not found number in our system
# 1 successful refresh
# 2 you can refresh once every 6 hours
# 4 is unknown error


def layan(number):
    url = "https://api.layan-t.net/api/Subscribtions/CustomersRefreshNumber"  # عدل الـ endpoint حسب API

    headers = {
        'Host': 'api.layan-t.net',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:149.0) Gecko/20100101 Firefox/149.0',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Content-Type': 'application/json',
        'LANG': 'ar',
        'Origin': 'https://rn.layan-t.net',
        'Referer': 'https://rn.layan-t.net/',
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache'
    }

    payload = {
        "number": number
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        # print(response.text)
        if 'لم يتم العثور على رقمك' in response.text:
            return 0
        elif 'يمكنك تحديث الرقم مرة كل خمس ساعات' in response.text:
            return 2
        elif 'تم ارسال طلبك بنجاح' in response.text:
            return 3
        else:
            return 4
    except Exception as e:
        return 4

# print(layan('0512509368'))

def aloha(phone_number):
    url = "https://refresh.telecom.co.il/home/refreshNumber"

    headers = {
        "Host": "refresh.telecom.co.il",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://refresh.telecom.co.il",
        "Referer": "https://refresh.telecom.co.il/home",
        "Connection": "keep-alive",
    }

    data = {
        "phone_number": phone_number
    }

    try:
        response = requests.post(url, headers=headers, data=data)
        print(response.text)
        if 'Wrong Numbe' in response.json()['message']:
            return 0
        elif 'number updated last 6 hours' in response.json()['message']:
            return 2
        elif 'Phone number refreshed' in response.json()['message']:
            return 1
        elif 'number waiting in queue' in response.json()['message']:
            return 2
        else:
            return 4
    except:
        return 4
# print(aloha("0515973340"))


def areen(number):
    url = "https://api.areen.net/api/common/RefreshMobileNumber"

    headers = {
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        "Content-Type": "application/json",
        "HX-Current-URL": "https://update.areen.net/",
        "HX-Request": "true",
        "HX-Target": "result",
        "HX-Trigger": "mobileForm",
        "Origin": "https://update.areen.net",
        "Referer": "https://update.areen.net/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "Connection": "keep-alive",
    }

    payload = {
        "MobNumber": number
    }


    try:
        response = requests.post(url, headers=headers, data=payload)
        # print(response.json())
        if response.json()['StatusCode'] == 993:
            return 2
        elif response.json()['StatusCode'] == 250:
            return 0
        elif response.json()['StatusCode'] == 23:
            return 1
        else:
            return 4
    except:
        return 4


# print(areen("0528066540"))
