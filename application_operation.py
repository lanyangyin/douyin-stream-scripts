import ctypes
import subprocess
import threading

# 尝试设置为“每显示器DPI感知”，这是最推荐的方式
try:
    # 2 = PROCESS_PER_MONITOR_DPI_AWARE
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception as e:
    # 如果上面的API不存在（如Win8.1以下），尝试旧版API
    try:
        # 1 = PROCESS_SYSTEM_DPI_AWARE
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except:
        # 终极备选方案：使用user32的旧API
        ctypes.windll.user32.SetProcessDPIAware()

import os
import time
from ctypes import windll
from typing import Union, Optional, Tuple, Dict, List

import cv2
import numpy as np
import win32api
import win32con
import win32gui
import win32ui
from PIL import Image
from cv2 import Mat


class WindowController:
    """窗口控制器类，用于处理窗口查找、截图、模板匹配和点击操作"""

    def __init__(self, launcher_path: str = r"C:\Program Files (x86)\webcast_mate\直播伴侣 Launcher.exe"):
        """
        初始化窗口控制器

        Args:
            launcher_path: 应用程序启动路径
        """
        self.img_tmp_dir = "img_tmp"
        self._set_dpi_awareness()
        self.launcher_path = launcher_path
        self.hwnd = None  # 当前操作的窗口句柄
        self.dpi_scale = 1.0  # DPI缩放比例
        self.last_screenshot = None  # 最后一张截图

    @staticmethod
    def _set_dpi_awareness():
        """设置DPI感知，确保截图和坐标计算的准确性"""
        try:
            # 2 = PROCESS_PER_MONITOR_DPI_AWARE
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception as e:
            try:
                # 1 = PROCESS_SYSTEM_DPI_AWARE
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except:
                # 终极备选方案：使用user32的旧API
                ctypes.windll.user32.SetProcessDPIAware()

    def find_window(self, class_name: str, window_name: str, start_program: bool = True,
                    timeout: int = 10, retry_interval: float = 1.0) -> Optional[int]:
        """
        查找指定窗口，如果找不到可以自动启动程序

        Args:
            class_name: 窗口类名
            window_name: 窗口标题
            start_program: 如果找不到窗口是否启动程序
            timeout: 查找超时时间（秒）
            retry_interval: 重试间隔（秒）

        Returns:
            窗口句柄或None
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            windows = self._get_windows(class_name, window_name)

            if windows:
                self.hwnd = windows[0]
                self.dpi_scale = self._get_dpi_scale(self.hwnd)
                return self.hwnd

            # 如果没找到窗口且允许启动程序
            if start_program and not windows:
                if self._start_program():
                    print(f"已启动程序，等待窗口出现...")

            time.sleep(retry_interval)

        print(f"❌ 在{timeout}秒内未找到窗口: {class_name} - {window_name}")
        return None

    @staticmethod
    def _get_windows(class_name: str, window_name: str) -> List[int]:
        """
        通过class和title获取窗口句柄

        Returns:
            窗口句柄列表
        """
        target_windows = []

        def enum_window_callback(hwnd, extra):
            """枚举窗口回调"""
            try:
                current_class = win32gui.GetClassName(hwnd)
                current_title = win32gui.GetWindowText(hwnd)

                if (current_class, current_title) == extra:
                    target_windows.append(hwnd)
            except:
                pass
            return True

        try:
            win32gui.EnumWindows(enum_window_callback, (class_name, window_name))
        except:
            pass

        return target_windows

    def _start_program(self) -> bool:
        """启动程序"""
        if not os.path.exists(self.launcher_path):
            print(f"❌ 程序路径不存在: {self.launcher_path}")
            return False

        try:
            subprocess.Popen(self.launcher_path)
            return True
        except Exception as e:
            print(f"❌ 启动程序失败: {e}")
            return False

    @staticmethod
    def _get_dpi_scale(hwnd) -> float:
        """精确获取窗口的DPI缩放比例"""
        try:
            # 方法1: 使用GetDpiForWindow (Windows 10 1607+)
            dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
            return dpi / 96.0
        except:
            try:
                # 方法2: 使用GetDpiForSystem作为备用
                dpi = ctypes.windll.user32.GetDpiForSystem()
                return dpi / 96.0
            except:
                try:
                    # 方法3: 通过窗口边框估算（兼容性方案）
                    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                    window_width = right - left

                    client_rect = win32gui.GetClientRect(hwnd)
                    client_width = client_rect[2]

                    if window_width > 0 and client_width > 0:
                        estimated_border = (window_width - client_width) / 2
                        if estimated_border > 5:
                            return estimated_border / 8.0
                except:
                    pass

        return 1.0

    def set_window_handle(self, hwnd: int):
        """设置当前操作的窗口句柄"""
        self.hwnd = hwnd
        self.dpi_scale = self._get_dpi_scale(hwnd)

    def set_img_tmp_dir(self, img_tmp_dir: str):
        """设置模板目录"""
        self.img_tmp_dir = img_tmp_dir

    def capture_window(self, save_to_file: Optional[str] = None) -> Optional[Image.Image]:
        """
        捕获当前窗口的截图

        Args:
            save_to_file: 可选，保存截图到文件

        Returns:
            PIL图像对象或None
        """
        if not self.hwnd:
            print("❌ 未设置窗口句柄")
            return None

        try:
            # 获取窗口位置和大小
            left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
            width = right - left
            height = bottom - top

            # 获取窗口设备上下文
            hwnd_dc = win32gui.GetWindowDC(self.hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()

            # 创建位图
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            save_dc.SelectObject(bitmap)

            # 捕获窗口内容
            result = windll.user32.PrintWindow(self.hwnd, save_dc.GetSafeHdc(), 3)

            if not result:
                print("❌ 窗口捕获失败")
                # 清理资源
                win32gui.DeleteObject(bitmap.GetHandle())
                save_dc.DeleteDC()
                mfc_dc.DeleteDC()
                win32gui.ReleaseDC(self.hwnd, hwnd_dc)
                return None

            # 转换为PIL图像
            bmpinfo = bitmap.GetInfo()
            bmpstr = bitmap.GetBitmapBits(True)

            im = Image.frombuffer(
                'RGB',
                (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRX', 0, 1
            )

            # 快速全黑检测
            if self._is_image_mostly_black(im, threshold=0.99):
                print("⚠️  截图可能为全黑或几乎全黑，可能是窗口最小化或不可见")
                # 清理资源
                win32gui.DeleteObject(bitmap.GetHandle())
                save_dc.DeleteDC()
                mfc_dc.DeleteDC()
                win32gui.ReleaseDC(self.hwnd, hwnd_dc)
                return None

            # 清理资源
            win32gui.DeleteObject(bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(self.hwnd, hwnd_dc)

            self.last_screenshot = im

            # 保存到文件（如果需要）
            if save_to_file:
                im.save(save_to_file)
                print(f"📸 截图已保存: {save_to_file}")

            return im

        except Exception as e:
            print(f"❌ 截图失败: {e}")
            return None

    def _is_image_mostly_black(self, image: Image.Image, threshold: float = 0.99) -> bool:
        """
        快速检测图像是否大部分为黑色

        Args:
            image: PIL图像对象
            threshold: 黑色像素比例阈值，默认为0.99（99%）

        Returns:
            如果大部分为黑色返回True，否则返回False
        """
        # 方法1：使用缩略图快速检测（最快）
        # 创建缩略图（大大减少像素数量，加快处理速度）
        thumbnail_size = (16, 16)  # 16x16足够检测大部分情况
        thumbnail = image.resize(thumbnail_size, Image.Resampling.NEAREST)

        # 转换为灰度图
        gray_thumb = thumbnail.convert('L')

        # 获取像素数据（使用numpy提高速度）
        import numpy as np
        pixels = np.array(gray_thumb)

        # 计算黑色像素比例（像素值<10视为黑色）
        black_pixel_count = np.sum(pixels < 10)
        total_pixels = pixels.size
        black_ratio = black_pixel_count / total_pixels

        # 如果黑色像素比例超过阈值，认为图像大部分为黑色
        if black_ratio >= threshold:
            return True

        # 方法2：采样检测（更快但可能不够准确）
        # 只在图像中采样部分像素
        width, height = image.size
        sample_points = 100  # 采样点数量

        # 生成随机采样点
        import random
        random.seed(0)  # 设置固定种子以便重现结果

        # 采样像素并检查
        dark_count = 0
        for _ in range(sample_points):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)

            # 获取像素值（RGB）
            pixel = image.getpixel((x, y))

            # 计算亮度（简单平均）
            brightness = sum(pixel) / 3

            # 如果亮度小于10，认为是黑色
            if brightness < 10:
                dark_count += 1

        # 如果大部分采样点都是黑色
        if dark_count / sample_points >= threshold:
            return True

        return False

    # 或者使用更快的版本（仅采样检测）：
    def _is_image_mostly_black_fast(self, image: Image.Image, threshold: float = 0.99) -> bool:
        """
        更快速检测图像是否大部分为黑色（仅采样）

        Args:
            image: PIL图像对象
            threshold: 黑色像素比例阈值，默认为0.99（99%）

        Returns:
            如果大部分为黑色返回True，否则返回False
        """
        width, height = image.size

        # 采样点数量（可根据图像大小调整）
        if width * height < 10000:
            sample_points = 50
        else:
            sample_points = 100

        # 预计算采样位置（避免在循环中生成随机数）
        import random
        random.seed(0)  # 固定种子

        # 生成采样位置
        sample_positions = [
            (random.randint(0, width - 1), random.randint(0, height - 1))
            for _ in range(sample_points)
        ]

        # 统计黑色像素数量
        dark_count = 0

        # 批量获取像素值（比单个getpixel快）
        pixels = image.load()  # 获取像素访问对象

        for x, y in sample_positions:
            try:
                pixel = pixels[x, y]
                # 如果是RGBA模式，只取RGB
                if len(pixel) == 4:
                    r, g, b, a = pixel
                else:
                    r, g, b = pixel

                # 计算亮度（加权平均，更符合人眼感知）
                brightness = 0.299 * r + 0.587 * g + 0.114 * b

                # 如果亮度小于阈值（15），认为是黑色
                if brightness < 15:
                    dark_count += 1

                    # 如果已经超过阈值，提前返回
                    if dark_count / sample_points >= threshold:
                        return True
            except:
                # 如果坐标越界，跳过
                continue

        return dark_count / sample_points >= threshold

    def load_template(self, template_path: str) -> Tuple[Optional[Mat], Optional[Tuple[int, int]]]:
        """
        加载模板图像

        Args:
            template_path: 模板图像文件名

        Returns:
            (模板图像, (宽度, 高度)) 或 (None, None)
        """
        full_path = os.path.join(self.img_tmp_dir, template_path)

        if not os.path.exists(full_path):
            print(f"❌ 模板文件不存在: {full_path}")
            return None, None

        try:
            template = cv2.imread(full_path, cv2.IMREAD_COLOR)
            if template is None:
                print(f"❌ 无法加载模板图像: {full_path}")
                return None, None

            template_h, template_w = template.shape[:2]
            return template, (template_w, template_h)
        except Exception as e:
            print(f"❌ 加载模板失败: {e}")
            return None, None

    def find_template(self, template_path: str, confidence: float = 0.7,
                      use_last_screenshot: bool = False,
                      click_position_ratio: tuple = (0.5, 0.5)) -> Optional[Dict]:
        """
        在当前窗口中查找模板图像

        Args:
            template_path: 模板图像路径
            confidence: 匹配置信度阈值
            use_last_screenshot: 是否使用最后一张截图
            click_position_ratio: 点击位置比例 (x_ratio, y_ratio)，范围0-1
                                  默认(0.5, 0.5)表示中心点
                                  (0, 0)表示左上角，(1, 1)表示右下角

        Returns:
            包含匹配信息的字典或None
        """
        if not self.hwnd:
            print("❌ 未设置窗口句柄")
            return None

        # 验证比例参数
        if not (0 <= click_position_ratio[0] <= 1 and 0 <= click_position_ratio[1] <= 1):
            print("❌ 点击位置比例必须在0到1之间")
            click_position_ratio = (0.5, 0.5)  # 使用默认值

        # 加载模板
        template, template_size = self.load_template(template_path)
        if template is None:
            return None

        # 获取截图
        if use_last_screenshot and self.last_screenshot:
            screenshot = self.last_screenshot
        else:
            screenshot = self.capture_window()
            if screenshot is None:
                return None

        # 调整DPI缩放
        screenshot_scaled = self._scale_screenshot_to_template_dpi(screenshot, self.dpi_scale)

        # 检查截图尺寸是否大于等于模板尺寸
        screenshot_width, screenshot_height = screenshot_scaled.size
        template_width, template_height = template_size

        if screenshot_width < template_width or screenshot_height < template_height:
            print(
                f"⚠️  截图尺寸({screenshot_width}x{screenshot_height})小于模板尺寸({template_width}x{template_height})，无法匹配")
            return None

        # 执行模板匹配
        try:
            match_result = self._match_template(screenshot_scaled, template, confidence)
        except cv2.error as e:
            print(f"❌ 模板匹配失败: {e}")
            return None

        if match_result[0] is None:
            return None

        # 计算坐标，传递点击位置比例
        coordinates = self._calculate_match_coordinates(
            match_result[0], template_size, self.dpi_scale,
            self.hwnd, click_position_ratio
        )

        if coordinates:
            coordinates.update({
                'confidence': match_result[1],
                'template_size': template_size,
                'template_path': template_path,
                'click_position_ratio': click_position_ratio
            })

        return coordinates

    @staticmethod
    def _scale_screenshot_to_template_dpi(screenshot_pil: Image.Image, scale_ratio: float) -> Image.Image:
        """将截图缩放到模板图像的DPI空间"""
        if abs(scale_ratio - 1.0) > 0.05:
            new_width = int(screenshot_pil.width / scale_ratio)
            new_height = int(screenshot_pil.height / scale_ratio)
            return screenshot_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)
        return screenshot_pil

    @staticmethod
    def _match_template(screenshot_pil: Image.Image, template: Mat, confidence: float = 0.7) -> Tuple:
        """在截图中执行模板匹配"""
        try:
            screenshot_cv = cv2.cvtColor(np.array(screenshot_pil), cv2.COLOR_RGB2BGR)
            result = cv2.matchTemplate(screenshot_cv, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if max_val < confidence:
                return None, None, None

            return max_loc, max_val, result.shape
        except cv2.error as e:
            print(f"❌ OpenCV模板匹配错误: {e}")
            return None, None, None
        except Exception as e:
            print(f"❌ 模板匹配异常: {e}")
            return None, None, None

    @staticmethod
    def _calculate_match_coordinates(match_loc: Tuple[int, int], template_size: Tuple[int, int],
                                     scale_ratio: float, hwnd: int,
                                     click_position_ratio: tuple = (0.5, 0.5)) -> Optional[Dict]:
        """
        计算匹配位置的各种坐标

        Args:
            match_loc: 模板匹配位置 (x, y)
            template_size: 模板大小 (width, height)
            scale_ratio: DPI缩放比例
            hwnd: 窗口句柄
            click_position_ratio: 点击位置比例 (x_ratio, y_ratio)

        Returns:
            包含坐标信息的字典或None
        """
        if match_loc is None:
            return None

        match_x, match_y = match_loc
        template_w, template_h = template_size

        # 根据比例计算点击位置
        # 示例：(0.5, 0.5) = 中心点，(0.25, 0.25) = 四分之一点
        click_x_scaled = match_x + int(template_w * click_position_ratio[0])
        click_y_scaled = match_y + int(template_h * click_position_ratio[1])

        # 转换回物理像素坐标
        click_x_physical = int(click_x_scaled * scale_ratio)
        click_y_physical = int(click_y_scaled * scale_ratio)

        # 窗口矩形信息
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)

        # 转换为屏幕坐标
        screen_x = left + click_x_physical
        screen_y = top + click_y_physical

        # 转换为窗口客户区坐标
        client_x, client_y = win32gui.ScreenToClient(hwnd, (screen_x, screen_y))

        return {
            'match_position_scaled': (match_x, match_y),
            'click_position_scaled': (click_x_scaled, click_y_scaled),
            'click_position_physical': (click_x_physical, click_y_physical),
            'screen_position': (screen_x, screen_y),
            'client_position': (client_x, client_y),
            'window_rect': (left, top, right, bottom),
            'click_position_ratio': click_position_ratio,
            'template_center_scaled': (match_x + template_w // 2, match_y + template_h // 2),
            'template_size': template_size
        }

    def click(self, x: int = None, y: int = None, coordinates: Dict = None,
              button: str = 'left', click_type: str = 'single') -> bool:
        """
        在窗口中点击

        Args:
            x, y: 窗口客户区坐标（如果提供coordinates，则优先使用coordinates）
            coordinates: 通过find_template返回的坐标字典
            button: 'left'/'right'/'middle' 鼠标按钮
            click_type: 'single'/'double' 单击/双击

        Returns:
            是否成功
        """
        if not self.hwnd:
            print("❌ 未设置窗口句柄")
            return False

        # 优先使用coordinates中的client_position
        if coordinates and 'client_position' in coordinates:
            x, y = coordinates['client_position']

        if x is None or y is None:
            print("❌ 未提供点击坐标")
            return False

        # 准备点击消息
        lParam = win32api.MAKELONG(x, y)

        if button == 'left':
            down_msg = win32con.WM_LBUTTONDOWN
            up_msg = win32con.WM_LBUTTONUP
            dbl_msg = win32con.WM_LBUTTONDBLCLK
        elif button == 'right':
            down_msg = win32con.WM_RBUTTONDOWN
            up_msg = win32con.WM_RBUTTONUP
            dbl_msg = win32con.WM_RBUTTONDBLCLK
        else:  # middle
            down_msg = win32con.WM_MBUTTONDOWN
            up_msg = win32con.WM_MBUTTONUP
            dbl_msg = win32con.WM_MBUTTONDBLCLK

        # 发送点击消息
        try:
            if click_type == 'double':
                win32gui.SendMessage(self.hwnd, dbl_msg, win32con.MK_LBUTTON, lParam)
                win32gui.SendMessage(self.hwnd, up_msg, 0, lParam)
            else:
                win32gui.SendMessage(self.hwnd, down_msg, win32con.MK_LBUTTON, lParam)
                time.sleep(0.05)
                win32gui.SendMessage(self.hwnd, up_msg, 0, lParam)

            return True
        except Exception as e:
            print(f"❌ 点击失败: {e}")
            return False

    def click_template(self, template_path: str, confidence: float = 0.7,
                       button: str = 'left', click_type: str = 'single',
                       click_position_ratio: tuple = (0.5, 0.5)) -> bool:
        """
        查找模板并点击

        Args:
            template_path: 模板图像路径
            confidence: 匹配置信度阈值
            button: 鼠标按钮
            click_type: 点击类型
            click_position_ratio: 点击位置比例 (x_ratio, y_ratio)
                                  默认(0.5, 0.5)表示中心点

        Returns:
            是否成功点击
        """
        coordinates = self.find_template(
            template_path,
            confidence,
            click_position_ratio=click_position_ratio
        )

        if not coordinates:
            print(f"❌ 未找到模板: {template_path}")
            return False

        return self.click(coordinates=coordinates, button=button, click_type=click_type)

    def get_window_info(self) -> Optional[Dict]:
        """获取当前窗口信息"""
        if not self.hwnd:
            return None

        try:
            title = win32gui.GetWindowText(self.hwnd)
            class_name = win32gui.GetClassName(self.hwnd)
            left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
            width = right - left
            height = bottom - top

            return {
                'hwnd': self.hwnd,
                'title': title,
                'class_name': class_name,
                'position': (left, top, right, bottom),
                'size': (width, height),
                'dpi_scale': self.dpi_scale
            }
        except:
            return None

# 检查"Chrome_WidgetWin_1", "直播伴侣"的窗口
Launcher_path = r"C:\Program Files (x86)\webcast_mate\直播伴侣 Launcher.exe"

controller = WindowController(Launcher_path)

controller.find_window("Chrome_WidgetWin_1", "直播伴侣")  # 启动直播伴侣

# for hwnd in controller._get_windows("Chrome_WidgetWin_1", "直播伴侣"):  # 区分主窗口，副窗口，遮罩窗口
#     controller.set_window_handle(hwnd)
#     ccw = controller.capture_window()
#     if ccw:
#         # ccw.show()
#         print(controller.find_template("sec_failed_resume_live.png"))

def start_live():
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
                if controller.click_template("main_start_living.png"):
                    continue
                if controller.click_template("main_live_stopped_return.png"):
                    continue
                if controller.click_template("sec_restore_live_broadcast_screen.png", 0.85, click_position_ratio=(0.75, 0.875)):
                    continue
                if controller.click_template("sec_failed_resume_live.png", 0.85, click_position_ratio=(0.75, 0.75)):
                    continue
                if controller.click_template("sec_no_sound_reminder.png", 0.85, click_position_ratio=(0.5, 0.875)):
                    continue
                if controller.click_template("sec_confirm_withdrawal.png", 0.85, click_position_ratio=(0.25, 0.875)):
                    continue
                if controller.click_template("sec_confirm_withdrawal_live.png", 0.85, click_position_ratio=(0.25, 0.875)):
                    continue
                if controller.click_template("sec_true_stop_live_is.png", 0.85, click_position_ratio=(0.25, 0.875)):
                    continue

start_live()
exit()
class glb:
    now_window_statue = {
        "main_windows": {
            "statue": False,
            "template_image": "live_streaming_partner.png",
            "introduction": "直播伴侣主窗口",
            "hwnd": 0,
        },
        "start_live_windows": {
            "statue": False,
            "template_image": "start_live.png",
            "introduction": "直播伴侣开始直播[按钮]窗口",
            "hwnd": 0,
        },
        "start_live_ing_windows": {
            "statue": False,
            "template_image": "start_live_ing.png",
            "introduction": "直播伴侣开始中…[按钮]窗口",
            "hwnd": 0,
        },
        "stop_live_windows": {
            "statue": False,
            "template_image": "stop_live.png",
            "introduction": "直播伴侣关播[按钮]窗口",
            "hwnd": 0,
        },
        "no_sound_reminder_windows": {
            "statue": False,
            "template_image": "no_sound_reminder.png",
            "introduction": "直播无声音[提示]窗口",
            "hwnd": 0,
        },
        "true_stop_live_is_windows": {
            "statue": False,
            "template_image": "true_stop_live_is.png",
            "introduction": "确认要结束当前直播吗？[提示]窗口",
            "hwnd": 0,
        },
        "live_ended_windows": {
            "statue": False,
            "template_image": "live_ended.png",
            "introduction": "直播伴侣直播已结束窗口",
            "hwnd": 0,
        },
        "confirm_withdrawal_windows": {
            "statue": False,
            "template_image": "confirm_withdrawal.png",
            "introduction": "确认退出吗？[提示]窗口",
            "hwnd": 0,
        },
        "restore_live_broadcast_screen_windows": {
            "statue": False,
            "template_image": "restore_live_broadcast_screen.png",
            "introduction": "恢复直播画面[提示]窗口",
            "hwnd": 0,
        },
        "failed_resume_live_windows": {
            "statue": False,
            "template_image": "failed_resume_live.png",
            "introduction": "恢复开播失败[提示]窗口",
            "hwnd": 0,
        },
    }
    old_window_statue = {
        "main_windows": {
            "statue": False,
            "template_image": "live_streaming_partner.png",
            "introduction": "直播伴侣主窗口",
            "hwnd": 0,
        },
        "start_live_windows": {
            "statue": False,
            "template_image": "start_live.png",
            "introduction": "直播伴侣开始直播[按钮]窗口",
            "hwnd": 0,
        },
        "start_live_ing_windows": {
            "statue": False,
            "template_image": "start_live_ing.png",
            "introduction": "直播伴侣开始中…[按钮]窗口",
            "hwnd": 0,
        },
        "stop_live_windows": {
            "statue": False,
            "template_image": "stop_live.png",
            "introduction": "直播伴侣关播[按钮]窗口",
            "hwnd": 0,
        },
        "no_sound_reminder_windows": {
            "statue": False,
            "template_image": "no_sound_reminder.png",
            "introduction": "直播无声音[提示]窗口",
            "hwnd": 0,
        },
        "true_stop_live_is_windows": {
            "statue": False,
            "template_image": "true_stop_live_is.png",
            "introduction": "确认要结束当前直播吗？[提示]窗口",
            "hwnd": 0,
        },
        "live_ended_windows": {
            "statue": False,
            "template_image": "live_ended.png",
            "introduction": "直播伴侣直播已结束窗口",
            "hwnd": 0,
        },
        "confirm_withdrawal_windows": {
            "statue": False,
            "template_image": "confirm_withdrawal.png",
            "introduction": "确认退出吗？[提示]窗口",
            "hwnd": 0,
        },
        "restore_live_broadcast_screen_windows": {
            "statue": False,
            "template_image": "restore_live_broadcast_screen.png",
            "introduction": "恢复直播画面[提示]窗口",
            "hwnd": 0,
        },
        "failed_resume_live_windows": {
            "statue": False,
            "template_image": "failed_resume_live.png",
            "introduction": "恢复开播失败[提示]窗口",
            "hwnd": 0,
        },
    }
    check_window_statue_is = False


def check_now() -> dict[str, Union[dict[str, Union[int, str, bool]], None]]:
    windows_hwnd = controller._get_windows("Chrome_WidgetWin_1", "直播伴侣")
    if windows_hwnd:
        for hwnd in windows_hwnd.copy():
            controller.set_window_handle(hwnd)
            placement = win32gui.GetWindowPlacement(hwnd)
            if placement[1] == win32con.SW_SHOWMINIMIZED:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)  # 正常显示窗口
            for windows in glb.now_window_statue.copy():
                coordinates = controller.find_template(template_path=glb.now_window_statue[windows]["template_image"])
                if coordinates:
                    glb.now_window_statue[windows]["statue"] = True
                    glb.now_window_statue[windows]["hwnd"] = hwnd
    else:
        return {}
    return glb.now_window_statue


check_now()
def thread_check_now():
    thread = threading.Thread(target=check_now)
    thread.daemon = True  # 设置为守护线程，主程序退出时会自动结束
    thread.start()


def time_check_now():
    glb.check_window_statue_is = True
    while glb.check_window_statue_is:
        thread_check_now()
        time.sleep(0.3)


thread = threading.Thread(target=time_check_now)
thread.daemon = True  # 设置为守护线程，主程序退出时会自动结束
thread.start()


def click_img(now_window_statue, wn, img):
    if now_window_statue[wn]["statue"]:
        hwnd = now_window_statue[wn]["hwnd"]
        controller.set_window_handle(hwnd)
        try:
            print(controller.click_template(img))
        except:
            return False
    return now_window_statue[wn]["statue"]


def start_live():
    start_live_is = False
    while not start_live_is:
        now_window_statue = glb.now_window_statue
        if now_window_statue:
            if now_window_statue["main_windows"]["statue"]:
                if now_window_statue["stop_live_windows"]["statue"]:
                    break
                click_img(now_window_statue, "start_live_windows", "start_live.png")
                click_img(now_window_statue, "live_ended_windows", "return.png")
                time.sleep(2)
                now_window_statue = glb.now_window_statue
                click_img(now_window_statue, "restore_live_broadcast_screen_windows","restore_live_broadcast_screen_true.png")
                click_img(now_window_statue, "failed_resume_live_windows", "failed_resume_live_true.png")
                click_img(now_window_statue, "no_sound_reminder_windows", "no_sound_reminder_true.png")
                click_img(now_window_statue, "confirm_withdrawal_windows", "confirm_withdrawal_cancel.png")
                click_img(now_window_statue, "true_stop_live_is_windows", "true_stop_live_is_cancel.png")
            else:
                # print("窗口未打开")
                pass
        else:
            # print("程序未启动")
            pass
            subprocess.run([Launcher_path])


def stop_live():
    stop_live_is = False
    while not stop_live_is:
        now_window_statue = glb.now_window_statue
        if now_window_statue:
            if now_window_statue["main_windows"]["statue"]:
                if now_window_statue["start_live_windows"]["statue"]:
                    stop_live_is = True
                    time.sleep(3)
                click_img(now_window_statue, "live_ended_windows", "return.png")
                click_img(now_window_statue, "stop_live_windows", "stop_live.png")
                time.sleep(2)
                now_window_statue = glb.now_window_statue
                if click_img(now_window_statue, "restore_live_broadcast_screen_windows",
                             "restore_live_broadcast_screen_true.png"):
                    stop_live_is = False
                if click_img(now_window_statue, "failed_resume_live_windows", "failed_resume_live_true.png"):
                    stop_live_is = False
                click_img(now_window_statue, "no_sound_reminder_windows", "no_sound_reminder_true.png")
                click_img(now_window_statue, "confirm_withdrawal_windows", "confirm_withdrawal_cancel.png")
                click_img(now_window_statue, "true_stop_live_is_windows", "true_stop_live_is_true.png")
            else:
                # print("窗口未打开")
                pass
        else:
            # print("程序未启动")
            pass
            subprocess.run([Launcher_path])


def clear_live():
    now_window_statue = glb.now_window_statue
    while now_window_statue:
        if now_window_statue["main_windows"]["statue"]:
            if click_img(now_window_statue, "confirm_withdrawal_windows", "confirm_withdrawal_true.png"):
                break
            else:
                try:
                    # 关闭窗口（向窗口发送关闭消息）[citation:10]
                    win32gui.PostMessage(now_window_statue["main_windows"]["hwnd"], win32con.WM_CLOSE, 0, 0)
                    time.sleep(1)
                except Exception as e:
                    pass
        else:
            # print("窗口未打开")
            pass
        now_window_statue = glb.now_window_statue

# 使用示例
# if __name__ == "__main__":
# start_time = time.time()
# hwnd = win32gui.GetForegroundWindow()
start_live()
# stop_live()
# clear_live()
# # 将窗口置于前台[citation:6]
# win32gui.SetForegroundWindow(hwnd)
# print(time.time() - start_time)
