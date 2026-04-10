"""
=========================================================
  AI-Based Face Authentication Web Login System
  app.py — Main Flask Application Entry Point
=========================================================
  This is the heart of the web application.
  It defines all URL routes and connects the frontend
  (HTML pages) with the backend logic (face recognition,
  database operations, session management).

  Routes defined here:
    /               → Home page
    /register       → New user registration (face capture)
    /login          → Face-based login page
    /do_register    → POST: Save user + capture face images
    /do_login       → POST: Run face recognition & authenticate
    /dashboard      → Protected user dashboard
    /admin          → Admin panel with login history
    /logout         → Clear session and redirect home
=========================================================
"""

from flask import (
    Flask, render_template, request,
    redirect, url_for, session, jsonify, flash
)
import os
import cv2
import numpy as np
import base64
import face_recognition
from datetime import datetime
from database import (
    get_db_connection, create_user,
    get_user_by_username, log_login_attempt,
    get_login_history, get_all_users
)

# ── App Configuration ──────────────────────────────────
app = Flask(__name__)

# Secret key is used to sign session cookies securely.
# In production, load this from environment variables!
app.secret_key = "face_auth_secret_key_2024_change_in_production"

# Allow up to 50 MB for registration requests containing Base64 face images
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

# Folder where face images are stored per user
DATASET_FOLDER = os.path.join(os.path.dirname(__file__), "dataset", "user_faces")
os.makedirs(DATASET_FOLDER, exist_ok=True)

# ── Helper: Save Base64 Image to Disk ──────────────────
def save_base64_image(b64_data, filepath):
    """
    Convert a Base64-encoded image string (from JS webcam)
    and save it as a .jpg file on disk.
    """
    # Strip the Data URI prefix if present: "data:image/jpeg;base64,..."
    if "," in b64_data:
        b64_data = b64_data.split(",")[1]
    img_bytes = base64.b64decode(b64_data)
    img_array = np.frombuffer(img_bytes, dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    if img is not None:
        cv2.imwrite(filepath, img)
        return True
    return False


# ── Helper: Load & Encode All Known Faces ──────────────
def load_known_faces():
    """
    Walk through the dataset/user_faces folder.
    For each user sub-folder, load every image,
    extract face encodings, and build two lists:
      - known_encodings : list of 128-dim face vectors
      - known_names     : corresponding username strings
    Returns both lists.
    """
    known_encodings = []
    known_names = []

    if not os.path.exists(DATASET_FOLDER):
        return known_encodings, known_names

    for username in os.listdir(DATASET_FOLDER):
        user_folder = os.path.join(DATASET_FOLDER, username)
        if not os.path.isdir(user_folder):
            continue

        for img_file in os.listdir(user_folder):
            if not img_file.lower().endswith((".jpg", ".jpeg", ".png")):
                continue

            img_path = os.path.join(user_folder, img_file)
            image = face_recognition.load_image_file(img_path)
            encodings = face_recognition.face_encodings(image)

            if encodings:
                # Take the first (and usually only) face in the image
                known_encodings.append(encodings[0])
                known_names.append(username)

    return known_encodings, known_names


# ══════════════════════════════════════════════════════
#  ROUTE: Home Page  →  GET /
# ══════════════════════════════════════════════════════
@app.route("/")
def index():
    """
    Render the landing page (index.html).
    Passes session info so the navbar can show
    logged-in user's name if already authenticated.
    """
    return render_template("index.html",
                           user=session.get("username"),
                           role=session.get("role"))


# ══════════════════════════════════════════════════════
#  ROUTE: Registration Page  →  GET /register
# ══════════════════════════════════════════════════════
@app.route("/register")
def register():
    """
    Render the registration page where the user fills
    in their details and captures their face via webcam.
    """
    return render_template("register.html")


# ══════════════════════════════════════════════════════
#  ROUTE: Handle Registration  →  POST /do_register
# ══════════════════════════════════════════════════════
@app.route("/do_register", methods=["POST"])
def do_register():
    """
    Process the registration form:
      1. Validate form fields (username, email, password)
      2. Check username doesn't already exist in DB
      3. Save user record to MySQL
      4. Save the captured face images (sent as Base64)
         to dataset/user_faces/<username>/
      5. Flash success/error message and redirect
    """
    username    = request.form.get("username", "").strip()
    email       = request.form.get("email", "").strip()
    full_name   = request.form.get("full_name", "").strip()
    password    = request.form.get("password", "").strip()
    face_images = request.form.getlist("face_images[]")   # List of Base64 strings

    # ── Basic Validation ─────────────────────────────
    if not username or not email or not password:
        flash("All fields are required.", "danger")
        return redirect(url_for("register"))

    if len(username) < 3:
        flash("Username must be at least 3 characters.", "danger")
        return redirect(url_for("register"))

    if len(face_images) < 5:
        flash("Please capture at least 5 face images.", "danger")
        return redirect(url_for("register"))


    # ── Check Username Uniqueness ────────────────────
    existing = get_user_by_username(username)
    if existing:
        flash(f"Username '{username}' is already taken.", "warning")
        return redirect(url_for("register"))

    # ── Save User to Database ────────────────────────
    user_id = create_user(username, email, full_name, password)
    if not user_id:
        flash("Database error. Please try again.", "danger")
        return redirect(url_for("register"))

    # ── Save Face Images to Disk ─────────────────────
    user_img_folder = os.path.join(DATASET_FOLDER, username)
    os.makedirs(user_img_folder, exist_ok=True)

    saved_count = 0
    for idx, b64_img in enumerate(face_images):
        filepath = os.path.join(user_img_folder, f"face_{idx+1:03d}.jpg")
        if save_base64_image(b64_img, filepath):
            saved_count += 1

    if saved_count == 0:
        flash("Face image saving failed. Try again.", "danger")
        return redirect(url_for("register"))

    flash(f"Registration successful! {saved_count} face images saved. "
          f"You can now login with your face.", "success")
    return redirect(url_for("login_page"))


# ══════════════════════════════════════════════════════
#  ROUTE: Login Page  →  GET /login
# ══════════════════════════════════════════════════════
@app.route("/login")
def login_page():
    """
    Render the face login page.
    If user is already logged in, redirect to dashboard.
    """
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return render_template("login.html")


# ══════════════════════════════════════════════════════
#  ROUTE: Handle Face Login  →  POST /do_login
# ══════════════════════════════════════════════════════
@app.route("/do_login", methods=["POST"])
def do_login():
    """
    Core face authentication logic:
      1. Receive a single Base64-encoded webcam frame
      2. Decode it to an OpenCV image
      3. Detect faces in the frame
      4. Compare detected face encoding against all
         stored face encodings (loaded from dataset/)
      5. If a match is found with confidence > threshold:
           - Set session variables
           - Log successful attempt to DB
           - Return JSON { success: true, username: ... }
      6. If no match / no face detected:
           - Log failed attempt to DB
           - Return JSON { success: false, message: ... }

    Returns JSON so the frontend JavaScript can handle
    the response without a full page reload.
    """
    data      = request.get_json()
    image_b64 = data.get("image", "")
    ip_addr   = request.remote_addr

    if not image_b64:
        return jsonify({"success": False, "message": "No image received."})

    # ── Decode Base64 image ──────────────────────────
    try:
        if "," in image_b64:
            image_b64 = image_b64.split(",")[1]
        img_bytes = base64.b64decode(image_b64)
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        frame     = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        # face_recognition expects RGB; OpenCV gives BGR
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    except Exception as e:
        return jsonify({"success": False, "message": f"Image decode error: {str(e)}"})

    # ── Detect faces in the frame ────────────────────
    face_locations = face_recognition.face_locations(rgb_frame)
    if not face_locations:
        log_login_attempt(None, ip_addr, "failed", "No face detected")
        return jsonify({"success": False,
                        "message": "No face detected. Please look directly at the camera."})

    # ── Encode the detected face ─────────────────────
    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
    if not face_encodings:
        return jsonify({"success": False,
                        "message": "Could not encode face. Try again."})

    # ── Load all known faces from dataset ───────────
    known_encodings, known_names = load_known_faces()
    if not known_encodings:
        return jsonify({"success": False,
                        "message": "No registered users found. Please register first."})

    # ── Compare face against known faces ─────────────
    # face_distance returns a float per known face:
    #   0.0 = perfect match, 1.0 = completely different
    # Threshold of 0.5 is a good balance for security.
    detected_encoding = face_encodings[0]
    face_distances    = face_recognition.face_distance(known_encodings, detected_encoding)
    best_match_idx    = int(np.argmin(face_distances))
    best_distance     = face_distances[best_match_idx]

    THRESHOLD = 0.50   # Lower = stricter matching

    if best_distance <= THRESHOLD:
        matched_username = known_names[best_match_idx]
        confidence       = round((1 - best_distance) * 100, 1)

        # Fetch full user record from DB
        user = get_user_by_username(matched_username)
        if not user:
            return jsonify({"success": False,
                            "message": "User record not found in database."})

        # ── Set session ──────────────────────────────
        session["logged_in"] = True
        session["username"]  = matched_username
        session["user_id"]   = user["id"]
        session["full_name"] = user["full_name"]
        session["role"]      = user["role"]

        # ── Log the successful attempt ───────────────
        log_login_attempt(user["id"], ip_addr, "success",
                          f"Confidence: {confidence}%")

        return jsonify({
            "success"    : True,
            "username"   : matched_username,
            "full_name"  : user["full_name"],
            "confidence" : confidence,
            "redirect"   : url_for("dashboard")
        })

    else:
        # Face detected but did NOT match any stored user
        log_login_attempt(None, ip_addr, "failed",
                          f"Unknown face. Best distance: {round(best_distance, 3)}")
        return jsonify({
            "success" : False,
            "message" : "⚠️ Unauthorized! Face not recognized. Access denied."
        })


# ══════════════════════════════════════════════════════
#  ROUTE: User Dashboard  →  GET /dashboard
# ══════════════════════════════════════════════════════
@app.route("/dashboard")
def dashboard():
    """
    Protected dashboard — only accessible when logged in.
    If not authenticated, redirect to login page.
    Shows the user's info and their own login history.
    """
    if not session.get("logged_in"):
        flash("Please login first.", "warning")
        return redirect(url_for("login_page"))

    user_id = session.get("user_id")
    history = get_login_history(user_id=user_id, limit=10)

    return render_template("dashboard.html",
                           username  = session.get("username"),
                           full_name = session.get("full_name"),
                           role      = session.get("role"),
                           history   = history)


# ══════════════════════════════════════════════════════
#  ROUTE: Admin Panel  →  GET /admin
# ══════════════════════════════════════════════════════
@app.route("/admin")
def admin_panel():
    """
    Admin-only panel. Accessible only to users whose
    role is 'admin' in the database.
    Shows: all users, full login history across all users.
    """
    if not session.get("logged_in"):
        flash("Please login first.", "warning")
        return redirect(url_for("login_page"))

    if session.get("role") != "admin":
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for("dashboard"))

    all_users   = get_all_users()
    all_history = get_login_history(user_id=None, limit=50)

    return render_template("admin.html",
                           username    = session.get("username"),
                           users       = all_users,
                           history     = all_history)


# ══════════════════════════════════════════════════════
#  ROUTE: Logout  →  GET /logout
# ══════════════════════════════════════════════════════
@app.route("/logout")
def logout():
    """
    Clear all session data and redirect to home page.
    """
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("index"))


# ══════════════════════════════════════════════════════
#  ROUTE: API — Check if username exists  →  POST /check_username
# ══════════════════════════════════════════════════════
@app.route("/check_username", methods=["POST"])
def check_username():
    """
    AJAX endpoint. Called by JavaScript on the register
    page to instantly tell the user if a username is taken.
    Returns JSON: { "available": true/false }
    """
    data     = request.get_json()
    username = data.get("username", "").strip()
    existing = get_user_by_username(username)
    return jsonify({"available": existing is None})


# ── Run the App ─────────────────────────────────────────
if __name__ == "__main__":
    # debug=True enables auto-reload and detailed error pages.
    # Set debug=False in production!
    app.run(debug=True, host="0.0.0.0", port=5000)
