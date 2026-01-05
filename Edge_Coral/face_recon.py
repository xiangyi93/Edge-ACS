import numpy as np
import cv2
import tensorflow.lite as tflite
import mysql.connector
import time
from datetime import datetime

# --- 1. 初始化模型與資料庫 ---
model_path = 'face_recognition.tflite'
interpreter = tflite.Interpreter(model_path=model_path)
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

# 使用 OpenCV 內建的人臉偵測器 (較輕量，適合當作觸發條件)
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def save_to_mysql(image, label, confidence):
    try:
        conn = mysql.connector.connect(
            host="rfid.cvqqawi4cgns.us-east-1.rds.amazonaws.com",
            user="admin",
            password="20260104",
            database="rfid"
        )
        cursor = conn.cursor()
        if label == "ling":
            print(f"授權使用者辨識成功: {label}，信心指數: {confidence:.2f}%")
            # sql = "INSERT INTO authorized_users (name, confidence) VALUES (%s, %s)"
            # val = (label, float(confidence))    
        else:
            # 將影像轉為二進位格式
            print(f"未授權使用者辨識: {label}，信心指數: {confidence:.2f}%，儲存影像中...")
            _, buffer = cv2.imencode('.jpg', image)
            img_blob = buffer.tobytes()
            sql = "INSERT INTO {} (name, confidence, image, timestamp) VALUES (%s, %s, %s, %s)".format("authorized_users" if label == "ling" else "unauthorized_user")
            val = (label, float(confidence), img_blob, datetime.now())
            
            cursor.execute(sql, val)
            conn.commit()
            print(f"資料已存入資料庫: {label}")
    except Exception as e:
        print(f"資料庫錯誤: {e}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# --- 2. 主程式迴圈 ---
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret: break

    # 轉灰階進行人臉偵測
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    # 判斷是否有人 (當 faces 列表不為空時)
    if len(faces) > 0:
        print("檢測到目標，開始身分辨識...")
        
        # 影像處理 (與你原本的邏輯相同)
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img_resized = cv2.resize(img_rgb, (224, 224))
        input_data = np.expand_dims(img_resized, axis=0).astype(np.float32) / 255.0

        interpreter.set_tensor(input_details[0]['index'], input_data)
        interpreter.invoke()
        output_data = interpreter.get_tensor(output_details[0]['index'])
        prediction = output_data[0][0]

        # 判定結果
        threshold = 0.4
        if prediction < threshold:
            result = "ling"
            confidence = (1 - prediction) * 100
        else:
            result = "other"
            confidence = prediction * 100

        # 顯示並儲存
        color = (0, 255, 0) if result == "ling" else (0, 0, 255)
        cv2.putText(frame, f"Captured: {result} {confidence:.1f}%", (10, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        cv2.imshow('Face Recognition', frame)
        cv2.waitKey(500) # 稍微停一下讓你看畫面

        # 執行儲存至資料庫
        save_to_mysql(frame, result, confidence)

        print("辨識完成，等待 2 秒...")
        print("=" * 30+"\n")
        time.sleep(2) # 暫停 2 秒
    
    else:
        # 如果沒人，僅顯示即時畫面
        cv2.putText(frame, "Waiting for person...", (10, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.imshow('Face Recognition', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()