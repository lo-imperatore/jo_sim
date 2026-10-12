#!/usr/bin/env python3
"""Lightweight YOLO detector for rosbag camera playback.

Subscribes to a sensor_msgs/Image topic, runs Ultralytics YOLO, and publishes:
  - annotated image (sensor_msgs/Image)
  - detections (vision_msgs/Detection2DArray)

Install deps inside the container once:
  pip install --break-system-packages ultralytics
"""

from __future__ import annotations

import sys

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2D, Detection2DArray, ObjectHypothesisWithPose


class YoloDetector(Node):
    def __init__(self) -> None:
        super().__init__('yolo_detector')

        self.declare_parameter('image_topic', '/front_camera/camera/color/image_raw')
        self.declare_parameter('annotated_topic', '/yolo/image_annotated')
        self.declare_parameter('detections_topic', '/yolo/detections')
        self.declare_parameter('model', 'yolov8n.pt')
        self.declare_parameter('confidence', 0.35)
        self.declare_parameter('device', 'cuda:0')
        self.declare_parameter('imgsz', 640)
        self.declare_parameter('max_fps', 10.0)

        image_topic = self.get_parameter('image_topic').get_parameter_value().string_value
        annotated_topic = self.get_parameter('annotated_topic').get_parameter_value().string_value
        detections_topic = self.get_parameter('detections_topic').get_parameter_value().string_value
        model_name = self.get_parameter('model').get_parameter_value().string_value
        self.confidence = self.get_parameter('confidence').get_parameter_value().double_value
        device = self.get_parameter('device').get_parameter_value().string_value
        self.imgsz = self.get_parameter('imgsz').get_parameter_value().integer_value
        max_fps = self.get_parameter('max_fps').get_parameter_value().double_value
        self.min_period = 1.0 / max_fps if max_fps > 0.0 else 0.0
        self._last_infer_time = 0.0

        try:
            from ultralytics import YOLO
        except ImportError as exc:
            self.get_logger().fatal(
                'ultralytics is not installed. Inside the container run:\n'
                '  pip install --break-system-packages ultralytics\n'
                f'Import error: {exc}'
            )
            raise SystemExit(1) from exc

        self.get_logger().info(f'Loading YOLO model "{model_name}" on device "{device}" ...')
        self.model = YOLO(model_name)
        # Warm-up / bind device. Fall back to CPU if CUDA is unavailable.
        try:
            self.device = device
            self.model.predict(
                np.zeros((self.imgsz, self.imgsz, 3), dtype=np.uint8),
                device=self.device,
                verbose=False,
            )
        except Exception as exc:  # noqa: BLE001 - hardware may lack CUDA
            self.get_logger().warn(f'CUDA device failed ({exc}); falling back to CPU')
            self.device = 'cpu'

        self.bridge = CvBridge()
        self.class_names = self.model.names

        # Bag camera is often best_effort; accept both.
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )

        self.pub_image = self.create_publisher(Image, annotated_topic, 10)
        self.pub_det = self.create_publisher(Detection2DArray, detections_topic, 10)
        self.sub = self.create_subscription(Image, image_topic, self._on_image, qos)

        self.get_logger().info(
            f'YOLO ready | sub={image_topic} | annotated={annotated_topic} | '
            f'detections={detections_topic} | device={self.device}'
        )

    def _on_image(self, msg: Image) -> None:
        now = self.get_clock().now().nanoseconds * 1e-9
        if self.min_period > 0.0 and (now - self._last_infer_time) < self.min_period:
            return
        self._last_infer_time = now

        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error(f'cv_bridge failed: {exc}')
            return

        results = self.model.predict(
            frame,
            conf=self.confidence,
            imgsz=self.imgsz,
            device=self.device,
            verbose=False,
        )
        result = results[0]

        det_array = Detection2DArray()
        det_array.header = msg.header

        annotated = frame.copy()
        if result.boxes is not None:
            for box in result.boxes:
                cls_id = int(box.cls.item())
                conf = float(box.conf.item())
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                cx = 0.5 * (x1 + x2)
                cy = 0.5 * (y1 + y2)
                w = x2 - x1
                h = y2 - y1
                label = self.class_names.get(cls_id, str(cls_id)) if isinstance(self.class_names, dict) else str(cls_id)

                det = Detection2D()
                det.header = msg.header
                det.bbox.center.position.x = cx
                det.bbox.center.position.y = cy
                det.bbox.size_x = w
                det.bbox.size_y = h
                hypo = ObjectHypothesisWithPose()
                hypo.hypothesis.class_id = label
                hypo.hypothesis.score = conf
                det.results.append(hypo)
                det_array.detections.append(det)

                cv2.rectangle(annotated, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                cv2.putText(
                    annotated,
                    f'{label} {conf:.2f}',
                    (int(x1), max(0, int(y1) - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    1,
                    cv2.LINE_AA,
                )

        self.pub_det.publish(det_array)
        out = self.bridge.cv2_to_imgmsg(annotated, encoding='bgr8')
        out.header = msg.header
        self.pub_image.publish(out)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = YoloDetector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main(sys.argv)
