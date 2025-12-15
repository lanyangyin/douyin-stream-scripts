import re
import time

import win32con
import win32gui

from src.stream_search import TsharkCapturer
from src.application_operation import WindowController


def start_live():
    """开始直播"""
    start_live_is = False
    while not start_live_is:
        controller.find_window("Chrome_WidgetWin_1", "直播伴侣")  # 启动直播伴侣
        for hwnd in controller._get_windows("Chrome_WidgetWin_1", "直播伴侣"):  # 区分主窗口，副窗口，遮罩窗口
            controller.set_window_handle(hwnd)
            placement = win32gui.GetWindowPlacement(hwnd)
            if placement[1] == win32con.SW_SHOWMINIMIZED:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)  # 正常显示窗口
                time.sleep(0.5)
            if controller.capture_window():
                if controller.find_template("main_stop_live.png"):
                    start_live_is = True
                    break
                if controller.click_template("main_start_live.png"):
                    continue
                if controller.click_template("main_live_stopped_return.png"):
                    continue
                if controller.click_template("sec_restore_live_broadcast_screen.png", 0.85,
                                             click_position_ratio=(0.75, 0.875)):
                    continue
                if controller.click_template("sec_failed_resume_live.png", 0.85, click_position_ratio=(0.75, 0.75)):
                    continue
                if controller.click_template("sec_no_sound_reminder.png", 0.85, click_position_ratio=(0.5, 0.875)):
                    continue
                if controller.click_template("sec_confirm_withdrawal.png", 0.85,
                                             click_position_ratio=(0.25, 0.875)):
                    continue
                if controller.click_template("sec_confirm_withdrawal_live.png", 0.85,
                                             click_position_ratio=(0.25, 0.875)):
                    continue
                if controller.click_template("sec_true_stop_live_is.png", 0.85, click_position_ratio=(0.25, 0.875)):
                    continue


def stop_live():
    """关闭直播"""
    stop_live_is = False
    while not stop_live_is:
        controller.find_window("Chrome_WidgetWin_1", "直播伴侣")  # 启动直播伴侣
        for hwnd in controller._get_windows("Chrome_WidgetWin_1", "直播伴侣"):  # 区分主窗口，副窗口，遮罩窗口
            controller.set_window_handle(hwnd)
            placement = win32gui.GetWindowPlacement(hwnd)
            if placement[1] == win32con.SW_SHOWMINIMIZED:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)  # 正常显示窗口
                time.sleep(0.5)
            if controller.capture_window():
                if controller.find_template("main_live_stopped_return.png"):
                    stop_live_is = True
                    break
                if controller.click_template("main_start_live.png"):
                    continue
                if controller.click_template("main_stop_live.png"):
                    continue
                if controller.click_template("sec_restore_live_broadcast_screen.png", 0.85,
                                             click_position_ratio=(0.75, 0.875)):
                    continue
                if controller.click_template("sec_failed_resume_live.png", 0.85, click_position_ratio=(0.75, 0.75)):
                    continue
                if controller.click_template("sec_no_sound_reminder.png", 0.85, click_position_ratio=(0.5, 0.875)):
                    continue
                if controller.click_template("sec_confirm_withdrawal.png", 0.85,
                                             click_position_ratio=(0.25, 0.875)):
                    continue
                if controller.click_template("sec_confirm_withdrawal_live.png", 0.85,
                                             click_position_ratio=(0.25, 0.875)):
                    continue
                if controller.click_template("sec_true_stop_live_is.png", 0.85, click_position_ratio=(0.75, 0.875)):
                    time.sleep(2)
                    continue


def clear_live():
    """关闭程序"""
    hwnds = controller._get_windows("Chrome_WidgetWin_1", "直播伴侣")
    while hwnds:
        for hwnd in hwnds:
            controller.set_window_handle(hwnd)
            placement = win32gui.GetWindowPlacement(hwnd)
            if placement[1] == win32con.SW_SHOWMINIMIZED:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)  # 正常显示窗口
                time.sleep(0.5)
            if controller.capture_window():
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)  # 关闭窗口（向窗口发送关闭消息）[citation:10]
                time.sleep(3)
        for hwnd in hwnds:
            controller.set_window_handle(hwnd)
            controller.click_template("sec_confirm_withdrawal.png", 0.85, click_position_ratio=(0.75, 0.875))
            controller.click_template("sec_confirm_withdrawal_live.png", 0.85, click_position_ratio=(0.75, 0.875))
        time.sleep(5)
        hwnds = controller._get_windows("Chrome_WidgetWin_1", "直播伴侣")


# 创建捕获器实例
capturer = TsharkCapturer()

# 获取网络接口
print("=== 可用的网络接口 ===")
interfaces = capturer.get_network_interfaces()
print(interfaces)
for iface in interfaces:
    if iface['is_physical']:
        print(f"{iface['index']}: {iface['label']}")

# 选择接口
while True:
    choice = input("\n请选择接口编号 (输入 'q' 退出): ").strip()
    if choice.lower() == 'q':
        exit()

    if capturer.set_interface(choice):
        break
    else:
        print("无效的接口编号，请重新选择")

capturer.set_filter(
    "rtmpt && "
    "(amf.string == \"connect\" || "
    "amf.string == \"releaseStream\" || "
    "amf.string == \"FCPublish\" || "
    "amf.string == \"publish\")"
)


# 设置输出回调函数（可选）
def on_packet_captured(packet_data: str):
    """数据包捕获回调函数"""
    print(f"捕获到数据包: {packet_data}")


capturer.set_output_callback(on_packet_captured)

# 开始捕获（非阻塞）
if capturer.start():
    print("捕获已启动，输入 'stop' 停止捕获...")
    # 主程序可以继续执行其他任务

    # 检查"Chrome_WidgetWin_1", "直播伴侣"的窗口
    Launcher_path = r"C:\Program Files (x86)\webcast_mate\直播伴侣 Launcher.exe"

    controller = WindowController(Launcher_path)
    controller.set_img_tmp_dir("img_tmp")


    start_live()
    clear_live()


    try:
        while True:
            cmd = input("输入命令 (stop/status/count/clear/exit): ").strip().lower()

            if cmd == 'stop':
                capturer.stop()

            elif cmd == 'status':
                print(f"正在捕获: {capturer.is_capturing()}")
                print(f"已捕获数据包数: {capturer.get_captured_count()}")

            elif cmd == 'count':
                print(f"已捕获数据包数: {capturer.get_captured_count()}")

            elif cmd == 'clear':
                capturer.clear_captured_data()
                print("已清空捕获数据")

            elif cmd == 'exit':
                if capturer.is_capturing():
                    capturer.stop()
                break

            elif cmd == 'data':
                data = capturer.get_captured_data()
                for i, packet in enumerate(data):
                    print(f"{i + 1}: {packet}")

            else:
                print("未知命令")

    except KeyboardInterrupt:
        print("\n收到中断信号")
        if capturer.is_capturing():
            capturer.stop()

else:
    print("启动捕获失败")


def extract_stream_info(raw_string):
    """
    从原始字符串中提取推流命令、推流码和服务器地址。

    参数:
        raw_string: 包含RTMP信息的原始字符串

    返回:
        一个列表，元素为字典，格式：[{'command': 命令, 'stream_code': 推流码, 'server': 服务器}, ...]
    """
    results = []

    # 1. 首先提取所有可能的服务器地址
    # 修改服务器地址的正则表达式，使其匹配完整的rtmp://地址
    # 现在支持匹配到逗号或行尾结束
    server_patterns = [
        r"tcUrl,(rtmp://[^,]+)",  # 匹配 tcUrl,rtmp://... 格式
        r"swfUrl,(rtmp://[^,]+)",  # 匹配 swfUrl,rtmp://... 格式
        # r"rtmp://[^,)'\"]+",  # 通用匹配 rtmp:// 地址
    ]

    server = None
    for pattern in server_patterns:
        server_match = re.search(pattern, raw_string)
        if server_match:
            server = server_match.group(1) if 'group' in dir(server_match) else server_match.group(0)
            break

    # 2. 定义匹配不同命令和其推流码的正则表达式
    # 匹配格式：command('stream-key?params')
    command_patterns = {
        'releaseStream': r"releaseStream\('([^']+)'\)",
        'FCPublish': r"FCPublish\('([^']+)'\)",
        'publish': r"publish\('([^']+)'\)",
        'connect': r"connect\('([^']+)'\)"  # 添加connect命令
    }

    # 3. 遍历所有命令模式进行匹配
    for command, pattern in command_patterns.items():
        matches = re.finditer(pattern, raw_string)
        for match in matches:
            stream_code = match.group(1)
            results.append({
                'command': command,
                'stream_code': stream_code,
                'server': server
            })

    # 4. 如果没有找到任何命令，但找到了服务器地址，返回服务器信息
    if not results and server:
        results.append({
            'command': 'server_only',
            'stream_code': None,
            'server': server
        })

    return results


for stream_info in extract_stream_info(",".join(capturer.get_captured_data())):
    print(stream_info['command'], stream_info['stream_code'], stream_info['server'])

print("\n捕获结束")
stop_live()
clear_live()
