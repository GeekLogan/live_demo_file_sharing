from flask import (
    Flask,
    request,
    send_from_directory,
    render_template_string,
    redirect,
    url_for,
    flash,
)
import os

import threading
import subprocess

FFMPEG_BIN = "./ffmpeg"  # Path to ffmpeg binary, ensure it's in your PATH or provide full path

job_queue = []
in_processing_queue = set() # Use a set to track files currently being processed
job_queue_lock = threading.Lock()

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 1000 MB limit
app.secret_key = "supersecretkey"  # Needed for flash messages

# Ensure upload folder exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

UPLOAD_FORM = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>File Sharing</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container py-5">
        <div class="row justify-content-center">
            <div class="col-md-8">
                <div class="card shadow">
                    <div class="card-header bg-primary text-white">
                        <h1 class="card-title mb-0">
                            <i class="bi bi-cloud-upload"></i> File Sharing
                        </h1>
                    </div>
                    <div class="card-body">
                        <!-- Upload Form -->
                        <div class="mb-4">
                            <h3 class="mb-3"><i class="bi bi-upload"></i> Upload a File</h3>
                            <form method="post" enctype="multipart/form-data" class="border rounded p-3 bg-light">
                                <div class="mb-3">
                                    <label for="file" class="form-label">Select File</label>
                                    <input type="file" name="file" id="file" class="form-control" required>
                                </div>
                                <div class="mb-3">
                                    <label for="filename" class="form-label">Custom File Name (optional)</label>
                                    <input type="text" name="filename" id="filename" class="form-control" placeholder="Leave empty to use original name">
                                    <div class="form-text">You can specify a custom name for the uploaded file. Include the file extension if needed.</div>
                                </div>
                                <button type="submit" class="btn btn-primary">
                                    <i class="bi bi-cloud-upload"></i> Upload File
                                </button>
                            </form>
                        </div>

                        <!-- Flash Messages -->
                        {% with messages = get_flashed_messages() %}
                          {% if messages %}
                            <div class="mb-4">
                                {% for message in messages %}
                                    <div class="alert alert-success alert-dismissible fade show" role="alert">
                                        <i class="bi bi-check-circle"></i> {{ message }}
                                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                                    </div>
                                {% endfor %}
                            </div>
                          {% endif %}
                        {% endwith %}

                        <!-- Available Files -->
                        <div>
                            <h3 class="mb-3"><i class="bi bi-files"></i> Available Files</h3>
                            {% if files %}
                                <div class="list-group">
                                    {% for filename in files %}
                                        <a href="{{ url_for('download_file', filename=filename) }}" 
                                           class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                                            <span>
                                                <i class="bi bi-file-earmark"></i> {{ filename }}
                                            </span>
                                            <i class="bi bi-download text-primary"></i>
                                        </a>
                                    {% endfor %}
                                </div>
                            {% else %}
                                <div class="alert alert-info" role="alert">
                                    <i class="bi bi-info-circle"></i> No files available for download yet.
                                </div>
                            {% endif %}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file part")
            return redirect(request.url)
        file = request.files["file"]
        if len(file.filename) == 0:
            flash("No selected file")
            return redirect(request.url)
        if file:
            # Get custom filename from form, or use original filename
            custom_filename = request.form.get("filename", "").strip()
            final_filename = file.filename.lower()

            if custom_filename:
                # Use custom filename, append the original file extension
                final_filename = custom_filename.lower() + '.' + file.filename.lower().split('.')[-1] 
            
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], final_filename)
            file.save(filepath)

            # Add the file to the job queue for processing
            with job_queue_lock:
                job_queue.append(filepath)

            flash(f"File uploaded successfully as {final_filename}!")
            return redirect(url_for("upload_file"))
        
    # GET request: render the upload form and list available files
    files = os.listdir(app.config["UPLOAD_FOLDER"])

    print(in_processing_queue)
    with job_queue_lock:
        # Remove files that are currently being processed
        files = [f for f in files if f not in in_processing_queue]

    return render_template_string(UPLOAD_FORM, files=files)


@app.route("/uploads/<path:filename>")
def download_file(filename):
    return send_from_directory(
        app.config["UPLOAD_FOLDER"], filename, as_attachment=True
    )

def background_worker():
    while True:
        with job_queue_lock:
            if job_queue:
                job = job_queue.pop(0)
            else:
                job = None

        if not job:
            # If no job is available, wait for a while before checking again
            threading.Event().wait(1)
            continue

        print("Processing job:", job)

        if job.lower().endswith(".mov"):
            # Convert iphone video to mp4
            #ffmpeg -i input.mov -c:v libx264 -preset fast -crf 23 -an output.mp4
            out_fname = job.replace('.mov', '') + '_converted.mp4'
            job = f'{FFMPEG_BIN} -i "{job}" -c:v libx264 -preset fast -crf 23 -an "{out_fname}"'
        else:
            continue

        try:
            # Example: run a shell command or process the job
            with job_queue_lock:
                in_processing_queue.add(out_fname)
            subprocess.run(job, shell=True)
            with job_queue_lock:
                if job in in_processing_queue:
                    in_processing_queue.remove(out_fname)
        except Exception as e:
            print(f"Error processing job: {e}")

        print(f"Finished processing job: {job}")

worker_thread = threading.Thread(target=background_worker, daemon=True)
worker_thread.start()

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=80)
