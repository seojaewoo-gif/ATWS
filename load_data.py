from ultralytics import YOLO

model = YOLO(r"day2_robot_gui\train\best.pt")  # 자동으로 구조/가중치 로드
print(model.info())  # 요약 정보
# 예시 추론
# results = model("test.jpg")
