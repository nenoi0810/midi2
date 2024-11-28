import requests
import rtmidi
import time
import os
from dotenv import load_dotenv

load_dotenv("config.env")

# OpenWeatherMap API設定
BASE_URL = "https://api.openweathermap.org/data/2.5/forecast"
API_KEY = os.getenv("API_KEY")
CITY = "Osaka,jp"

# 天気に対応する色
WEATHER_COLORS = {
    "Clear": (127, 63, 0),   # オレンジ
    "Clouds": (63, 63, 63),  # 灰色
    "Rain": (0, 127, 127)    # 水色
}

# 天気ごとのイラスト（8×8マトリックスデザイン）
WEATHER_PATTERNS = {
    "Clear": [
        "X......X",
        "..XXXX..",
        ".XX..XX.",
        ".X.XX.X.",
        ".X.XX.X.",
        ".XX..XX.",
        "..XXXX..",
        "X......X"
    ],
    "Clouds": [
        "........",
        "........",
        "..XXXXX.",
        ".XXXXXX.",
        "XXXXXXXX",
        ".XXXXXX.",
        "..XXXXX.",
        "........"
    ],
    "Rain": [
        "........",
        "..X.X.X.",
        ".X.X.X..",
        "........",
        ".XXXXXX.",
        "..XXXX..",
        "..XXXX..",
        "........"
    ]
}

# 状態管理
toggle_states = {"81": False, "84": False, "87": False}  # ボタンの状態を保持

# MIDI初期化
midiout = rtmidi.MidiOut()
midiin = rtmidi.MidiIn()
available_ports = midiout.get_ports()

if not available_ports:
    print("利用可能なMIDIポートが見つかりません。")
    exit(1)

print("利用可能なMIDIポート:")
for i, port in enumerate(available_ports):
    print(f"{i}: {port}")

# Launchpad Miniのポート番号を選択
port_number = 1
if port_number >= len(available_ports):
    print(f"指定したポート番号 {port_number} は無効です。")
    exit(1)

midiout.open_port(port_number)
midiin.open_port(port_number)
print(f"MIDIポート '{available_ports[port_number]}' を開きました。")

# Programmerモードに切り替え（エラーを無視して続行）
programmer_mode_message = [0xF0, 0x00, 0x20, 0x29, 0x02, 0x0D, 0x0E, 0x01, 0xF7]
try:
    midiout.send_message(programmer_mode_message)
    print("Programmerモードに切り替えました。")
except Exception as e:
    print(f"Programmerモード切替メッセージ送信エラー: {e}")

# SysExメッセージ生成
def create_sysex_message(lighting_type, led_index, *color_data):
    message = [0xF0, 0x00, 0x20, 0x29, 0x02, 0x0D, 0x03, lighting_type, led_index]
    message.extend(color_data)
    message.append(0xF7)
    return message

def send_sysex_message(message):
    try:
        for byte in message:
            midiout.send_message([byte])
        print("SysExメッセージを送信しました。")
    except Exception as e:
        print(f"SysEx送信エラー: {e}")


# 遅延付きLED設定
def set_led_color_with_delay(led_index, red, green, blue, delay=0.01):
    lighting_type = 3
    sysex_message = create_sysex_message(lighting_type, led_index, red, green, blue)
    try:
        midiout.send_message(sysex_message)
        time.sleep(delay)
    except Exception as e:
        print(f"LED点灯メッセージ送信エラー: {e}")

# 8×8マトリックスを描画
def draw_weather_pattern(pattern, color):
    for row in range(8):
        for col in range(8):
            led_index = row * 10 + col + 11
            if pattern[row][col] == "X":
                set_led_color_with_delay(led_index, *color)
            else:
                set_led_color_with_delay(led_index, 0, 0, 0)

# 8×8マトリックスを全消灯
def clear_matrix():
    for row in range(8):
        for col in range(8):
            led_index = row * 10 + col + 11
            set_led_color_with_delay(led_index, 0, 0, 0)

# 天気情報を取得
def get_weather():
    try:
        response = requests.get(f"{BASE_URL}?q={CITY}&appid={API_KEY}&units=metric")
        if response.status_code == 200:
            data = response.json()
            forecasts = data["list"]
            today_weather = forecasts[0]["weather"][0]["main"]
            tomorrow_weather = forecasts[8]["weather"][0]["main"]  # 約24時間後
            day_after_tomorrow_weather = forecasts[16]["weather"][0]["main"]  # 約48時間後
            return today_weather, tomorrow_weather, day_after_tomorrow_weather
        else:
            print(f"エラー: {response.status_code}, {response.text}")
            return None, None, None
    except Exception as e:
        print(f"リクエスト中にエラーが発生しました: {e}")
        return None, None, None

# 天気を表示
def display_weather():
    today, tomorrow, day_after_tomorrow = get_weather()
    if not today or not tomorrow or not day_after_tomorrow:
        print("天気情報の取得に失敗しました。")
        return

    # 天気に対応する色を取得
    today_color = WEATHER_COLORS.get(today, (0, 0, 0))
    tomorrow_color = WEATHER_COLORS.get(tomorrow, (0, 0, 0))
    day_after_tomorrow_color = WEATHER_COLORS.get(day_after_tomorrow, (0, 0, 0))

    # 天気表示
    for led_index in [81, 82, 71, 72]:
        set_led_color_with_delay(led_index, *today_color)
    for led_index in [84, 85, 74, 75]:
        set_led_color_with_delay(led_index, *tomorrow_color)
    for led_index in [87, 88, 77, 78]:
        set_led_color_with_delay(led_index, *day_after_tomorrow_color)

# 天気を表示するLEDインデックス
WEATHER_LED_INDICES = {
    "today": [81, 82, 71, 72],           # 今日の天気
    "tomorrow": [84, 85, 74, 75],        # 明日の天気
    "day_after_tomorrow": [87, 88, 77, 78]  # 明後日の天気
}

# 3日間の天気表示を消灯
def clear_weather_display():
    for indices in WEATHER_LED_INDICES.values():
        for led_index in indices:
            set_led_color_with_delay(led_index, 0, 0, 0)

# 3日間の天気を表示
def display_weather():
    today, tomorrow, day_after_tomorrow = get_weather()
    if not today or not tomorrow or not day_after_tomorrow:
        print("天気情報の取得に失敗しました。")
        return

    # 天気に対応する色を取得
    today_color = WEATHER_COLORS.get(today, (0, 0, 0))
    tomorrow_color = WEATHER_COLORS.get(tomorrow, (0, 0, 0))
    day_after_tomorrow_color = WEATHER_COLORS.get(day_after_tomorrow, (0, 0, 0))

    # 今日の天気
    for led_index in WEATHER_LED_INDICES["today"]:
        set_led_color_with_delay(led_index, *today_color)

    # 明日の天気
    for led_index in WEATHER_LED_INDICES["tomorrow"]:
        set_led_color_with_delay(led_index, *tomorrow_color)

    # 明後日の天気
    for led_index in WEATHER_LED_INDICES["day_after_tomorrow"]:
        set_led_color_with_delay(led_index, *day_after_tomorrow_color)

# ボタン押下時の動作（イラストと天気切り替え）
def handle_button_press(note):
    global toggle_states

    # イラストが表示中の場合
    if toggle_states[note]:
        print(f"ボタン {note}: イラスト表示中 -> 天気表示に戻ります。")
        clear_matrix()  # 全消灯
        display_weather()  # 天気表示に戻る
        toggle_states[note] = False  # 状態を天気表示に戻す
    else:  # 天気が表示中の場合
        print(f"ボタン {note}: 天気表示中 -> イラスト表示に切り替えます。")
        clear_weather_display()  # 3日間の天気表示を消す
        clear_matrix()  # 全消灯
        # 該当する天気データを取得してイラストを表示
        weather_index = {"81": 0, "84": 1, "87": 2}  # 今日・明日・明後日のインデックス
        weather = get_weather()[weather_index[note]]
        if weather in WEATHER_PATTERNS:
            pattern = WEATHER_PATTERNS[weather]
            color = WEATHER_COLORS.get(weather, (0, 0, 0))
            draw_weather_pattern(pattern, color)
        toggle_states[note] = True  # イラスト表示状態に切り替え


# メインループ
def main():
    display_weather()  # プログラム開始時に3日間の天気を表示

    print("ボタンを押して天気を確認してください。")
    while True:
        msg = midiin.get_message()
        if msg:
            message, _ = msg
            if message[0] == 144:  # Note On
                note = str(message[1])
                if note in ["81", "84", "87"]:
                    handle_button_press(note)  # ボタン押下処理を実行

if __name__ == "__main__":
    main()
