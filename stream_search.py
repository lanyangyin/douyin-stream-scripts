import json
import re
import subprocess
import threading
import time
from typing import List, Tuple, Optional, Callable, Any, Union


class TsharkCapturer:
    """RTMPT数据包捕获器类"""

    def __init__(self, tshark_path: str = r'C:\Program Files\Wireshark\tshark.exe'):
        """
        初始化Tshark捕获器

        参数:
            tshark_path: tshark可执行文件路径
        """
        self.tshark_path = tshark_path
        self.process = None
        self.capturing = False
        self.thread = None
        self.output_callback = None
        self.interface = None
        self.filter_expression = None
        self.fields = []
        self.captured_data = []
        self.default_fields = [
            'frame.number',
            'frame.time',
            '_ws.col.protocol',
            '_ws.col.info',
            'ip.src',
            'ip.dst',
            'tcp.srcport',
            'tcp.dstport',
            'amf.string'
        ]
        self.separator = ";"

    @staticmethod
    def parse_interfaces_to_dict_list(interface_list):
        """
        将接口列表转换为字典列表格式

        参数:
            interface_list (list): 包含接口信息的字符串列表

        返回:
            list: 元素为字典的列表，每个字典包含接口信息
        """
        result = []

        for item in interface_list:
            # 初始化字典
            interface_dict: dict[str, Optional[Union[str, int]]] = {
                'value': None,
                'label': None,
                'index': None,
                'type': None,
                'is_virtual': None,
                'is_physical': None
            }

            # 提取索引号（如果存在）
            index_match = re.match(r'^(\d+)\.\s*', item)
            if index_match:
                interface_dict['index'] = int(index_match.group(1))
                # 移除索引号和点
                item = re.sub(r'^\d+\.\s*', '', item)

            # 提取设备路径和标签
            # 格式通常是：设备路径 (标签) 或者 只有标签

            # 检查是否有括号包含标签
            label_match = re.search(r'\((.*?)\)$', item)

            if label_match:
                # 有标签的情况
                interface_dict['label'] = label_match.group(1)

                # 提取设备路径（括号前的内容，去掉末尾空格）
                value_part = re.sub(r'\s*\(.*?\)$', '', item).strip()

                # 检查是否看起来像设备路径（包含\或/）
                if '\\' in value_part or '/' in value_part or value_part in ['ciscodump', 'etwdump', 'randpkt',
                                                                             'sshdump.exe', 'udpdump', 'wifidump.exe']:
                    interface_dict['value'] = value_part
                else:
                    # 如果value_part不是设备路径，可能是只有标签的情况
                    interface_dict['value'] = None
            else:
                # 没有标签的情况，整个字符串作为设备路径
                interface_dict['value'] = item.strip()

            # 确定接口类型
            label = interface_dict['label']
            value = interface_dict['value']

            if label:
                label_lower = label.lower()

                # 根据标签判断类型
                if '以太网' in label or '本地连接' in label or 'ethernet' in label_lower:
                    interface_dict['type'] = '以太网'
                elif 'wlan' in label_lower or '无线' in label_lower or 'wi-fi' in label_lower:
                    interface_dict['type'] = 'WLAN'
                elif '蓝牙' in label_lower or 'bluetooth' in label_lower:
                    interface_dict['type'] = '蓝牙'
                elif 'vmware' in label_lower:
                    interface_dict['type'] = 'VMware虚拟接口'
                elif 'vethernet' in label_lower or 'hyper-v' in label_lower:
                    interface_dict['type'] = 'Hyper-V虚拟接口'
                elif 'wsl' in label_lower:
                    interface_dict['type'] = 'WSL虚拟接口'
                elif 'loopback' in label_lower:
                    interface_dict['type'] = '回环接口'
                elif 'usb' in label_lower:
                    interface_dict['type'] = 'USB接口'
                elif 'remote' in label_lower or 'cisco' in label_lower or 'ssh' in label_lower or 'udp' in label_lower:
                    interface_dict['type'] = '远程捕获接口'
                elif 'random' in label_lower:
                    interface_dict['type'] = '随机包生成器'
                elif 'event tracing' in label_lower:
                    interface_dict['type'] = 'ETW接口'
                else:
                    interface_dict['type'] = '未知接口'
            else:
                # 根据设备路径判断类型
                if value:
                    if 'NPF_Loopback' in value:
                        interface_dict['type'] = '回环接口'
                    elif 'USBPcap' in value:
                        interface_dict['type'] = 'USB接口'
                    elif 'ciscodump' in value:
                        interface_dict['type'] = '远程捕获接口'
                    elif 'etwdump' in value:
                        interface_dict['type'] = 'ETW接口'
                    elif 'randpkt' in value:
                        interface_dict['type'] = '随机包生成器'
                    elif 'sshdump.exe' in value:
                        interface_dict['type'] = 'SSH远程捕获'
                    elif 'udpdump' in value:
                        interface_dict['type'] = 'UDP监听器'
                    elif 'wifidump.exe' in value:
                        interface_dict['type'] = 'Wi-Fi远程捕获'
                    else:
                        interface_dict['type'] = '未知接口'

            # 判断是否为虚拟接口
            if interface_dict['type']:
                type_str = interface_dict['type'].lower()
                is_virtual = ('虚拟' in interface_dict['type'] or
                              'vmware' in type_str or
                              'hyper-v' in type_str or
                              'wsl' in type_str or
                              'loopback' in type_str or
                              'remote' in type_str or
                              '随机' in interface_dict['type'] or
                              'etw' in type_str)

                interface_dict['is_virtual'] = is_virtual

                # 物理接口通常是：以太网、WLAN、蓝牙、USB接口
                is_physical = ('以太网' in interface_dict['type'] or
                               'WLAN' in interface_dict['type'] or
                               '蓝牙' in interface_dict['type'] or
                               'USB接口' in interface_dict['type'])

                interface_dict['is_physical'] = is_physical
            else:
                interface_dict['is_virtual'] = None
                interface_dict['is_physical'] = None

            result.append(interface_dict)

        return result

    def get_network_interfaces(self) -> Union[tuple[list[Any], dict[Any, Any]], list[Any]]:
        """获取可用的网络接口列表"""
        try:
            result = subprocess.run(
                [self.tshark_path, '-D'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )

            if result.returncode == 0:
                interfaces = []
                interfaces_json = {}
                lines = result.stdout.strip().split('\n')

                # 转换为字典列表
                interface_dicts = self.parse_interfaces_to_dict_list(lines)
                return interface_dicts
            else:
                return []
        except Exception as e:
            print(f"获取网络接口时出错: {e}")
            return []

    def set_interface(self, interface_num: str) -> bool:
        """
        设置要监听的网络接口

        参数:
            interface_num: 接口编号

        返回:
            是否设置成功
        """
        interfaces = self.get_network_interfaces()
        interface_nums = [str(iface['index']) for iface in interfaces]

        if interface_num in interface_nums:
            self.interface = interface_num
            return True
        else:
            print(f"错误: 接口编号 {interface_num} 不存在")
            return False

    def set_filter(self, filter_expression: str):
        """
        设置过滤器表达式

        参数:
            filter_expression: 过滤器表达式
        """
        self.filter_expression = filter_expression

    def set_fields(self, fields: List[str]):
        """
        设置要捕获的字段

        参数:
            fields: 字段列表，如 ['frame.number', 'ip.src', 'ip.dst']
        """
        self.fields = fields

    def add_field(self, field: str):
        """添加一个要捕获的字段"""
        if field not in self.fields:
            self.fields.append(field)

    def remove_field(self, field: str):
        """移除一个要捕获的字段"""
        if field in self.fields:
            self.fields.remove(field)

    def set_output_callback(self, callback: Callable[[str], None]):
        """
        设置输出回调函数，每捕获到一行数据就会调用

        参数:
            callback: 回调函数，接收一个字符串参数（捕获到的数据行）
        """
        self.output_callback = callback

    def _capture_thread(self):
        """捕获线程函数"""
        if not self.interface:
            print("错误: 未设置网络接口")
            return

        if not self.filter_expression:
            print("错误: 未设置过滤器表达式")
            return

        # 使用默认字段或自定义字段
        fields_to_use = self.fields if self.fields else self.default_fields

        # 构建命令
        command = [
            self.tshark_path,
            '-i', self.interface,
            '-Y', self.filter_expression,
            '-l',  # 实时输出
            '-T', 'fields'
        ]

        # 添加字段
        for field in fields_to_use:
            command.extend(['-e', field])

        # 添加分隔符
        command.extend(['-E', f'separator={self.separator}'])

        print(f"开始捕获数据包...")
        print(f"接口: {self.interface}")
        print(f"过滤器: {self.filter_expression}")
        print(f"字段: {', '.join(fields_to_use)}")

        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='ignore',
                bufsize=1
            )

            # 读取输出
            for line in self.process.stdout:
                if not self.capturing:
                    break

                if line.strip():
                    self.captured_data.append(line.strip())

                    # 如果有回调函数，调用它
                    if self.output_callback:
                        self.output_callback(line.strip())

                    # 实时打印输出（可选）
                    # print(line.strip())

            # 等待进程结束
            self.process.wait()

        except Exception as e:
            print(f"捕获过程中出错: {e}")

        finally:
            self.capturing = False
            if self.process and self.process.poll() is None:
                self.process.terminate()

    def start(self) -> bool:
        """
        开始捕获数据包（非阻塞方式）

        返回:
            是否成功启动
        """
        if self.capturing:
            print("捕获已在运行中")
            return False

        if not self.interface:
            print("请先设置网络接口")
            return False

        self.capturing = True
        self.thread = threading.Thread(target=self._capture_thread)
        self.thread.daemon = True  # 设置为守护线程，主程序退出时会自动结束
        self.thread.start()

        return True

    def stop(self):
        """停止捕获数据包"""
        if not self.capturing:
            print("捕获未在运行中")
            return

        print("正在停止捕获...")
        self.capturing = False

        # 终止进程
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                # 等待进程结束
                for _ in range(10):
                    if self.process.poll() is not None:
                        break
                    time.sleep(0.1)
                else:
                    if self.process.poll() is None:
                        self.process.kill()
            except Exception as e:
                print(f"停止进程时出错: {e}")

        # 等待线程结束
        if self.thread:
            self.thread.join(timeout=2)

        print("捕获已停止")

    def is_capturing(self) -> bool:
        """检查是否正在捕获"""
        return self.capturing

    def get_captured_data(self) -> List[str]:
        """获取已捕获的数据"""
        return self.captured_data.copy()

    def clear_captured_data(self):
        """清空已捕获的数据"""
        self.captured_data.clear()

    def get_captured_count(self) -> int:
        """获取已捕获的数据包数量"""
        return len(self.captured_data)


# 使用示例
if __name__ == "__main__":
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

    # 设置自定义字段（可选）
    # capturer.set_fields(['frame.number', 'ip.src', 'ip.dst', 'tcp.srcport', 'tcp.dstport'])

    # 设置输出回调函数（可选）
    def on_packet_captured(packet_data: str):
        """数据包捕获回调函数"""
        print(f"捕获到数据包: {packet_data}")


    capturer.set_output_callback(on_packet_captured)

    # 开始捕获（非阻塞）
    if capturer.start():
        print("捕获已启动，输入 'stop' 停止捕获...")
        # 主程序可以继续执行其他任务
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

