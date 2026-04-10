"""
=========================================================
  recognize_face.py — Face Recognition Engine
=========================================================
  PURPOSE:
    This module is a standalone face recognition tool
    that can be used to test face matching independently
    from the web app.

    The same logic is used inside app.py's /do_login route,
    but this script lets you test it via command line.

  HOW IT WORKS — The Science:
    1. face_recognition uses dlib's deep learning model
       (ResNet-34 trained on ~3 million faces).

    2. For each face image, it extracts a 128-dimensional
       "embedding" — a list of 128 numbers that uniquely
       describe the geometry of that face.

    3. To check if two faces match, it computes the
       Euclidean distance between their embeddings.
       Distance < 0.6 → same person (typically)
       We use 0.5 for higher security.

    4. Unknown faces (distance > threshold) are rejected.

  HOW TO RUN (standalone test):
    python recognize_face.py
=========================================================
"""

import face_recognition
import cv2
import numpy as np
import os
import sys
import time


# ── Configuration ──────────────────────────────────────
DATASET_DIR     = os.path.join(os.path.dirname(__file__), "dataset", "user_faces")
MATCH_THRESHOLD = 0.50     # Lower = stricter. Range: 0.0 (exact) to 1.0 (anything)
FRAME_SCALE     = 0.5      # Downscale frames for faster detection


# ══════════════════════════════════════════════════════
#  load_known_faces()
#  Walk the dataset folder and build encoding lists.
# ══════════════════════════════════════════════════════
def load_known_faces(dataset_path: str = DATASET_DIR):
    """
    Scan dataset/user_faces/ and return:
      known_encodings : list of 128-dim numpy arrays
      known_names     : list of username strings

    Each folder in dataset_path is one user.
    We skip images with no detectable face.

    Example folder structure:
      dataset/user_faces/
        alice/
          face_001.jpg
          face_002.jpg
        bob/
          face_001.jpg
    """
    known_encodings = []
    known_names     = []

    if not os.path.exists(dataset_path):
        print(f"[WARNING] Dataset folder not found: {dataset_path}")
        return known_encodings, known_names

    user_folders = [
        d for d in os.listdir(dataset_path)
        if os.path.isdir(os.path.join(dataset_path, d))
    ]

    if not user_folders:
        print("[WARNING] No user folders found in dataset.")
        return known_encodings, known_names

    print(f"[INFO] Loading encodings for {len(user_folders)} user(s)...")

    for username in user_folders:
        user_dir    = os.path.join(dataset_path, username)
        img_files   = [
            f for f in os.listdir(user_dir)
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ]

        user_count = 0
        for img_file in img_files:
            img_path = os.path.join(user_dir, img_file)
            try:
                # Load image — returns a numpy RGB array
                image = face_recognition.load_image_file(img_path)

                # Extract face encodings (128-dim vectors)
                # Usually 1 face per image → take index [0]
                encodings = face_recognition.face_encodings(image)
                if encodings:
                    known_encodings.append(encodings[0])
                    known_names.append(username)
                    user_count += 1

            except Exception as e:
                print(f"  [SKIP] {img_file}: {e}")

        print(f"  ✓ {username}: {user_count}/{len(img_files)} images encoded")

    print(f"[INFO] Total encodings loaded: {len(known_encodings)}\n")
    return known_encodings, known_names


# ══════════════════════════════════════════════════════
#  recognize_from_frame(frame, known_encodings, known_names)
#  Detect and recognize faces in a single OpenCV frame.
# ══════════════════════════════════════════════════════
def recognize_from_frame(frame, known_encodings, known_names):
    """
    Given an OpenCV BGR frame, returns a list of dicts:
      [
        {
          "name"      : "alice" (or "Unknown"),
          "distance"  : 0.38,
          "confidence": 62.0,
          "location"  : (top, right, bottom, left)
        },
        ...
      ]
    One dict per detected face.
    """
    results = []

    # Downscale for faster processing
    small_frame = cv2.resize(frame, (0, 0),
                             fx=FRAME_SCALE,
                             fy=FRAME_SCALE)

    # Convert BGR (OpenCV) → RGB (face_recognition)
    rgb_small = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    # Detect face bounding boxes
    # model="hog" → faster, CPU-only
    # model="cnn" → slower, more accurate, GPU recommended
    face_locations = face_recognition.face_locations(rgb_small, model="hog")

    if not face_locations:
        return results

    # Compute encodings for detected faces
    face_encodings = face_recognition.face_encodings(rgb_small, face_locations)

    for encoding, location in zip(face_encodings, face_locations):
        name       = "Unknown"
        distance   = 1.0
        confidence = 0.0

        if known_encodings:
            # Compute Euclidean distance to ALL known faces
            distances     = face_recognition.face_distance(known_encodings, encoding)
            best_idx      = int(np.argmin(distances))
            best_distance = float(distances[best_idx])

            if best_distance <= MATCH_THRESHOLD:
                name       = known_names[best_idx]
                distance   = best_distance
                confidence = round((1.0 - best_distance) * 100, 1)

        # Scale location back to original frame size
        top, right, bottom, left = location
        scale = int(1 / FRAME_SCALE)
        location_orig = (top * scale, right * scale,
                         bottom * scale, left * scale)

        results.append({
            "name"      : name,
            "distance"  : distance,
            "confidence": confidence,
            "location"  : location_orig
        })

    return results


# ══════════════════════════════════════════════════════
#  draw_results(frame, results)
#  Draw labeled bounding boxes on the frame.
# ══════════════════════════════════════════════════════
def draw_results(frame, results):
    """
    For each recognized face:
      - Green box + name label → known user
      - Red box + "UNAUTHORIZED" → unknown face
    """
    for face in results:
        top, right, bottom, left = face["location"]
        name       = face["name"]
        confidence = face["confidence"]

        is_known = name != "Unknown"
        color    = (0, 220, 0) if is_known else (0, 0, 220)

        # Bounding box
        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)

        # Label background
        cv2.rectangle(frame, (left, bottom - 35),
                      (right, bottom), color, cv2.FILLED)

        # Label text
        label = f"{name} ({confidence}%)" if is_known else "⚠ UNAUTHORIZED"
        cv2.putText(frame, label, (left + 5, bottom - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    return frame


# ══════════════════════════════════════════════════════
#  run_live_recognition()
#  Open webcam and run real-time face recognition.
# ══════════════════════════════════════════════════════
def run_live_recognition():
    """
    Standalone demo: opens the webcam and shows live
    face recognition with labeled bounding boxes.
    Press 'Q' to quit.
    """
    print("=" * 55)
    print("  Live Face Recognition Test — Face Auth System")
    print("=" * 55)

    # Load all stored face encodings from dataset/
    known_encodings, known_names = load_known_faces()
    if not known_encodings:
        print("[ERROR] No known faces loaded. Register users first.")
        sys.exit(1)

    # Open webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Cannot open webcam.")
        sys.exit(1)

    print("\n[INFO] Webcam open. Running recognition...")
    print("[INFO] Press Q to quit.\n")

    process_every_n = 3   # Only analyze every 3rd frame (speed optimization)
    frame_count     = 0
    last_results    = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        # Process every Nth frame for speed
        if frame_count % process_every_n == 0:
            last_results = recognize_from_frame(
                frame, known_encodings, known_names
            )

        # Always draw the last results
        frame = draw_results(frame, last_results)

        # Show FPS hint
        cv2.putText(frame, "Press Q to quit", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)

        cv2.imshow("Face Recognition — Live Test", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("\n[INFO] Recognition stopped.")


# ── Main ────────────────────────────────────────────────
if __name__ == "__main__":
    run_live_recognition()
