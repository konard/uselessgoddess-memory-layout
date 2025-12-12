import cv2
import numpy as np
import math
import sys
from pathlib import Path

# Добавляем src в путь
sys.path.append(str(Path(__file__).parents[1] / "src"))

from states.match.impl.detector import MinimapDirectionDetector, MinimapConfig


def rotate_image(image, angle):
  """Вращает изображение вокруг центра без обрезки (вписывая в квадрат)"""
  image_center = tuple(np.array(image.shape[1::-1]) / 2)
  rot_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
  result = cv2.warpAffine(
    image,
    rot_mat,
    image.shape[1::-1],
    flags=cv2.INTER_LINEAR,
    borderValue=(0, 0, 0),
  )
  return result


def run_benchmark():
  img_path = "resources/radar.png"

  original_radar = cv2.imread(img_path)

  print("--- REALISTIC MINIMAP BENCHMARK ---")
  print("Controls:")
  print(" [A/D] Rotate Radar")
  print(" [Space] Toggle Auto-Rotate")
  print(" [Q] Quit")

  cfg = MinimapConfig()

  original_radar = cv2.resize(original_radar, (cfg.x, cfg.y))

  detector = MinimapDirectionDetector(cfg)

  cv2.namedWindow("Minimap Lab")

  def nothing(x):
    pass

  # Ползунки для настройки "на лету"
  cv2.createTrackbar("Threshold", "Minimap Lab", cfg.threshold, 255, nothing)
  cv2.createTrackbar("Brightness", "Minimap Lab", 0, 100, nothing)

  angle = 0
  auto_rotate = True

  while True:
    # 1. Обновляем параметры
    detector.config.threshold = cv2.getTrackbarPos("Threshold", "Minimap Lab")
    brightness_add = cv2.getTrackbarPos("Brightness", "Minimap Lab")

    # 2. Подготовка кадра
    if auto_rotate:
      angle = (angle + 2) % 360

    # Вращаем исходник
    # Угол в OpenCV идет против часовой стрелки.
    rotated_radar = rotate_image(original_radar, angle)

    # Симуляция изменения яркости (например, флешка или карта Nuke)
    if brightness_add > 0:
      rotated_radar = cv2.convertScaleAbs(
        rotated_radar, alpha=1, beta=brightness_add
      )

    # Создаем полный экран и вставляем радар в угол (эмуляция игры)
    full_screen = np.zeros((600, 800, 3), dtype=np.uint8)
    h, w = rotated_radar.shape[:2]
    full_screen[0:h, 0:w] = rotated_radar

    # 3. ДЕТЕКЦИЯ
    # Детектор пытается найти поворот стрелки.
    # Т.к. мы вращали картинку на `angle`, стрелка должна быть повернута на `angle`.
    # Примечание: CS2 координаты могут отличаться (90 смещение), но относительная разница должна быть верной.
    detected_angle = detector.extract_rotation(full_screen, visuals=False)

    # 4. Визуализация
    display = full_screen.copy()
    center = (w // 2, h // 2)

    # Вектор "Истины" (куда мы повернули картинку)
    # OpenCV вращает против часовой. 0 градусов - это "право" в тригонометрии, но "верх" для image processing обычно требует -90.
    # Если исходная стрелка смотрела ВВЕРХ:
    # Angle=0 -> Вверх. Angle=90 (CCW) -> Влево.
    # Математически для отрисовки линии:
    real_rad = math.radians(-angle - 90)
    real_end = (
      int(center[0] + 70 * math.cos(real_rad)),
      int(center[1] + 70 * math.sin(real_rad)),
    )
    cv2.arrowedLine(display, center, real_end, (0, 255, 0), 2, cv2.LINE_AA)

    # Вектор "Детектора"
    if detected_angle is not None:
      # Детектор обычно возвращает 0..360.
      # Нужно согласовать системы координат.
      # Если твой детектор возвращает угол 0=East, 90=South, то:
      det_rad = math.radians(detected_angle)
      # Иногда нужен оффсет, зависит от реализации extract_rotation (-90 или +90)
      # Проверь визуально: если красная и зеленая линии совпадают - всё ок.

      # Попробуем стандартный маппинг
      det_end = (
        int(center[0] + 50 * math.cos(det_rad)),
        int(center[1] + 50 * math.sin(det_rad)),
      )
      cv2.arrowedLine(display, center, det_end, (0, 0, 255), 2, cv2.LINE_AA)

      cv2.putText(
        display,
        f"Angle: {angle}",
        (220, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0),
        2,
      )
      cv2.putText(
        display,
        f"Det:   {detected_angle:.1f}",
        (220, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 255),
        2,
      )
    else:
      cv2.putText(
        display,
        "LOST ARROW",
        (220, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 255),
        2,
      )

    # --- DEBUG MASK ---
    # Показываем то, что видит алгоритм (черно-белую маску)
    gray = cv2.cvtColor(rotated_radar, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(
      gray, detector.config.threshold, 255, cv2.THRESH_BINARY
    )

    # Рисуем ROI, если он используется в детекторе
    # (Просто для наглядности рисуем квадрат в центре маски)
    roi_size = 40
    cv2.rectangle(
      mask,
      (center[0] - roi_size, center[1] - roi_size),
      (center[0] + roi_size, center[1] + roi_size),
      (128),
      1,
    )

    cv2.imshow("Minimap Lab", display)
    cv2.imshow("Binary Mask", mask)

    key = cv2.waitKey(30)
    if key & 0xFF == ord("q"):
      break
    elif key & 0xFF == ord(" "):
      auto_rotate = not auto_rotate
    elif key & 0xFF == ord("a"):
      angle = (angle + 5) % 360
      auto_rotate = False
    elif key & 0xFF == ord("d"):
      angle = (angle - 5) % 360
      auto_rotate = False

  cv2.destroyAllWindows()


if __name__ == "__main__":
  run_benchmark()
