from openai import OpenAI
import base64
import os
import json
from datetime import datetime
import mimetypes
# 사진 형식 바꾸는거 시간 남으면 구현해보자...지금은 그냥 이름만 변경

# API 키 불러오기
BASE_DIR = os.path.dirname(__file__)   # day2_robot_gui/api
KEY_PATH = os.path.join(BASE_DIR, "api_key.txt")

with open(KEY_PATH, "r", encoding="utf-8") as f:
    api_key = f.read().strip()
client = OpenAI(api_key=api_key)

# 고정 클래스임 / 원하는 detection label 지정
LABELS = ["미상물체", "무인기", "쓰레기 풍선", "새"]
"""
class 별 임의 고정값
# 미상물체          : 모두 모름
# 무인기            : 속도만 알수 있음(feat. 방공무기의 레이저 거리 측정기)
# 쓰레기 풍선       : 풍속 api 받아올까?`
# 새                : 속도만 알수 있음(feat. 방공무기의 레이저 거리 측정기)
"""
CLASS_META = {
    "미상물체"      : {'speed' : "불명", 'direction' : "불명", "altitude" : "불명", "distance" : "불명"},
    "무인기"        : {'speed' : "30~160km/h", 'direction' : "불명", "altitude" : "불명", "distance" : "불명"},
    "쓰레기 풍선"   : {'speed' : "풍속수준", 'direction' : "불명", "altitude" : "불명", "distance" : "불명"},
    "새"            : {'speed' : "30~90km/h", 'direction' : "불명", "altitude" : "불명", "distance" : "불명"}
}
# 간결하게 : 단일 라벨 + conf 값 나와야함
SYS_MSG = """
You must classify the image into exactly one of these labels:
["미상물체", "무인기", "쓰레기 풍선", "새"].
Do not output any reasoning.
Return only a label and a confidence (0–1 float).
"""


# (MVP) 분류 제한해! (MVP)
def _content_rule(prmpt : str, base64_image:str, image_path:str):
    """
    1. 모델은 항상 사전 정의해둔 LABELS 에서만 출력
    2. 분류 기준 : 
    3. conf 값도 반환
    """
    mime, _ =  mimetypes.guess_type(image_path)
    mime = mime or "image/jpeg"
    guidance = (
        """
        you always classify image just one class, after you analyze a label below :
        ["미상물체", "무인기", "쓰레기 풍선", "새"]
        - result format is (label: string, confidence: 0~1 float)
        - Do not output reasoning sentences
        - If uncertain, classify it as "미상물체"
        - confidence should reasonably assigned depending on the clarity
        """
    )
    return [
        {'type' : "text", "text" : f"{prmpt}\n\n{guidance}"},
        {"type" : "image_url", "image_url" : {"url" : f"data:{mime};base64,{base64_image}"}}
    ]

def _make_report(location, username, label, now):
    # default 는 미상물체
    meta = CLASS_META.get(label, CLASS_META["미상물체"])
    # 보고는 시간이 생명!!
    when        = now.strftime("%H:%M")
    title       = f"{location} {label} 관측보고"
    what        = f"{label}, <속도 : {meta['speed']}, 방향 : {meta['direction']}>"
    where       = f"<거리 : {meta['distance']}, 고도 : {meta['altitude']}>"
    
    # 보고 양식
    report = (
        f"제  목 : {title}\n"
        f"언  제 : {when}\n"
        f"무엇을 : {what}\n"
        f"어디서 : {where}\n"
        f"누  가 : {username}\n"
    )
    return report


def get_image_description(image_path, prompt):
    """
    return ()
    라벨    : str(4개 클래스 중 하나) , 
    정확도  : 0~1,
    보고문  : 관측보고 포맷 == _content_rule 함수 참고
    raw 예문: 원문임
    )
    
    예외 : 1. 파일 못 열때, 2. tool_calls(이 api가 정의해둔 함수 쓸때 인자) 없으면 원문 보내기
    + 모르겠으면 미상물체로 다 처리해 버림 / 호랑이 사진 넣으면 미상물체..ㄷㄷ
    """
    try:        
        with open(image_path, "rb") as f:
            image_data = f.read()
    except FileNotFoundError:
        return f"이미지 경로 잘못 됐습니다.{image_path}"
    except OSError as e:
        return f"이미지 파일 열 수 없습니다.{image_path}\n{e}"
    base64_image = base64.b64encode(image_data).decode("utf-8")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            # 모델은 항상 이런 대답
            {"role": "system", "content" : SYS_MSG},
            # user(나)는 항상 이런 입력
            {"role": "user", "content": _content_rule(prompt, base64_image, image_path)}
            ],
        tools = [
    {
        "type": "function",
        "function": {
            "name": "image_describer",
            "description": "Reasoning what this picture is. Return fixed label and confidence",
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description":"identify label one of ['미상물체', '무인기', '쓰레기 풍선', '새']"},
                    "confidence": {"type": "number", "description":"0~1 float"}
                },
                "required": ["label", "confidence"]
            }
        }
    }
],
        tool_choice={"type": "function", "function":{"name":"image_describer"}}
        ,
        max_tokens=100
    )
    msg = response.choices[0].message
    # print(response)
    label = "미상물체"
    conf = 0.0
    raw_content = getattr(msg, "content", None)
    
    
    if getattr(msg, "tool_calls", None):
        call = msg.tool_calls[0]
        if call.type == "function" and call.function.name == "image_describer":
            args = json.loads(call.function.arguments)  # 문자열 JSON → dict
            label = args.get("label", "unknown")
            conf = args.get("confidence")
            
            report = _make_report("000방공진지", os.getlogin(), label, datetime.now())
            
            head = f"{label}" if conf is None else f"{label} (conf:{conf:.2f})"
            return f"{head}\n{report}"
    
    # 폴백: 그래도 없으면 content 사용
    raw = msg.content or "(설명을 받지 못했습니다)"
    return raw


    # return response.choices[0].message.content
