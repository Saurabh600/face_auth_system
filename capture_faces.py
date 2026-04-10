"""
=========================================================
  capture_faces.py — Standalone Face Capture Script
=========================================================
  PURPOSE:
    This is an OPTIONAL standalone script you can run
    separately from the web app. It opens your webcam,
    detects your face using OpenCV's Haar Cascade,
    and saves 30 images to:
        dataset/user_faces/<username>/

  WHY BOTH THIS AND THE WEB APP?
    The web app captures faces via the browser's webcam
    (JavaScript → Base64 → Flask). This script does the
    same thing but from the command line — useful for
    testing face capture independently.

  HOW TO RUN:
    python capture_faces.py

  LIBRARIES USED:
    - OpenCV (cv2): camera access, Haar face detection,
                    image display, file saving
=========================================================
"""

import cv2
import os
import time
import sys

# ── Configuration ──────────────────────────────────────
DATASET_DIR   = os.path.join(os.path.dirname(__file__), "dataset", "user_faces")
IMAGES_TO_CAPTURE = 30     # How many face images to collect
CAPTURE_DELAY     = 0.3    # Seconds between captures (avoid duplicates)
MIN_FACE_SIZE     = (80, 80)  # Ignore tiny/far-away faces


def capture_faces_for_user(username: str):
    """
    Open the webcam and capture face images for a given user.

    Steps:
      1. Load OpenCV's pre-trained face detector (Haar Cascade).
         This XML file ships with OpenCV — no training needed!
      2. Open the default camera (index 0).
      3. Loop:
           a. Read a frame from the camera
           b. Convert to grayscale (faster detection)
           c. Detect face rectangles
           d. Draw green rectangle around face for feedback
           e. Every CAPTURE_DELAY seconds, save the image
      4. Stop after IMAGES_TO_CAPTURE images are saved.
      5. Release camera and close windows.
    """

    # ── Create output folder ───────────────────────────
    save_dir = os.path.join(DATASET_DIR, username)
    os.makedirs(save_dir, exist_ok=True)
    print(f"\n[INFO] Saving images to: {save_dir}")

    # ── Load Haar Cascade face detector ───────────────
    # cv2.data.haarcascades is the folder bundled with OpenCV
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)

    if face_cascade.empty():
        print("[ERROR] Could not load Haar Cascade XML file!")
        sys.exit(1)

    # ── Open webcam ────────────────────────────────────
    cap = cv2.VideoCapture(0)   # 0 = default camera
    if not cap.isOpened():
        print("[ERROR] Cannot access webcam. Is it connected?")
        sys.exit(1)

    print(f"[INFO] Webcam opened. Capturing {IMAGES_TO_CAPTURE} images...")
    print("[INFO] Look at the camera. Press 'Q' to quit early.\n")

    count       = 0
    last_saved  = time.time()

    while count < IMAGES_TO_CAPTURE:
        ret, frame = cap.read()
        if not ret:
            print("[WARNING] Failed to read frame. Retrying...")
            continue

        # ── Convert to grayscale for detection ─────────
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # ── Detect faces ───────────────────────────────
        # Parameters:
        #   scaleFactor=1.1  → how much image is scaled each pass
        #   minNeighbors=5   → how many neighbor rectangles needed
        #   minSize          → ignore faces smaller than this
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor  = 1.1,
            minNeighbors = 5,
            minSize      = MIN_FACE_SIZE
        )

        face_found = len(faces) > 0

        # ── Draw rectangles & info text ─────────────────
        for (x, y, w, h) in faces:
            color = (0, 255, 0) if face_found else (0, 0, 255)
            cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)

        status_text = f"Captured: {count}/{IMAGES_TO_CAPTURE}"
        cv2.putText(frame, status_text, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

        face_status = "Face Detected!" if face_found else "No Face — Look at Camera"
        cv2.putText(frame, face_status, (10, 65),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 255, 0) if face_found else (0, 0, 255), 2)

        cv2.putText(frame, f"User: {username}", (10, 95),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        cv2.imshow("Face Capture — Press Q to Quit", frame)

        # ── Save image every CAPTURE_DELAY seconds ──────
        now = time.time()
        if face_found and (now - last_saved) >= CAPTURE_DELAY:
            filename = f"face_{count+1:03d}.jpg"   # e.g. face_001.jpg
            filepath = os.path.join(save_dir, filename)
            cv2.imwrite(filepath, frame)
            count     += 1
            last_saved = now
            print(f"  Saved ({count}/{IMAGES_TO_CAPTURE}): {filename}")

        # ── Allow quit with 'Q' key ─────────────────────
        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("\n[INFO] Capture stopped early by user.")
            break

    # ── Cleanup ────────────────────────────────────────
    cap.release()
    cv2.destroyAllWindows()

    print(f"\n✅ Done! {count} images saved for user '{username}'")
    print(f"   Location: {save_dir}")


# ── Main entry point ────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  Face Capture Tool — Face Auth System")
    print("=" * 50)

    username = input("\nEnter username to capture faces for: ").strip()
    if not username:
        print("[ERROR] Username cannot be empty.")
        sys.exit(1)

    if len(username) < 3:
        print("[ERROR] Username must be at least 3 characters.")
        sys.exit(1)

    capture_faces_for_user(username)
