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
import pathlib

FFMPEG_BIN = (
    "./ffmpeg"  # Path to ffmpeg binary, ensure it's in your PATH or provide full path
)

job_queue = []
in_processing_queue = set()  # Use a set to track files currently being processed
job_queue_lock = threading.Lock()

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 1000 MB limit
app.secret_key = "supersecretkey"  # Needed for flash messages

# Ensure upload folder exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

UPLOAD_FORM = """
<!doctype html>
<html lang="en" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>File Sharing</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        body {
            background-color: #0a0a0a !important;
        }
        .card {
            background-color: #2a2a2a;
            border: 1px solid #444;
        }
        .card-header {
            background-color: #0d6efd !important;
            border-bottom: 1px solid #444;
        }
        .bg-light {
            background-color: #3a3a3a !important;
        }
        .list-group-item {
            background-color: #3a3a3a;
            border-color: #505050;
            color: #ffffff;
        }
        .list-group-item:hover {
            background-color: #505050;
        }
        .form-control {
            background-color: #3a3a3a;
            border-color: #505050;
            color: #ffffff;
        }
        .form-control:focus {
            background-color: #3a3a3a;
            border-color: #0d6efd;
            color: #ffffff;
            box-shadow: 0 0 0 0.25rem rgba(13, 110, 253, 0.25);
        }
        .alert-info {
            background-color: #1e4a6b;
            border-color: #3a6fb0;
            color: #cde8ff;
        }
        .alert-secondary {
            background-color: #3a3a3a;
            border-color: #505050;
            color: #ffffff;
        }
        .alert-success {
            background-color: #1a5e2a;
            border-color: #32b545;
            color: #e2f5e7;
        }
        .form-text {
            color: #c5c5c5;
        }
        .text-primary {
            color: #66b3ff !important;
        }
    </style>
</head>
<body class="bg-dark">
    <div class="container py-5">
        <div class="row justify-content-center">
            <div class="col-md-8">
                <div class="card shadow">
                    <div class="card-header bg-primary text-white">
                        <h1 class="card-title mb-0">
                            Neurons Can Fly Upload Portal
                        </h1>
                    </div>
                    <div class="card-body">
                        <!-- Upload Form -->
                        <div class="mb-4">
                            <h3 class="mb-3 text-white"><i class="bi bi-upload"></i> Upload a File</h3>
                            <form method="post" enctype="multipart/form-data" class="border rounded p-3 bg-light">
                                <div class="mb-3">
                                    <label for="file" class="form-label text-white">Select File</label>
                                    <input type="file" name="file" id="file" class="form-control" required>
                                </div>
                                <div class="mb-3">
                                    <label for="filename" class="form-label text-white">Custom File Name (optional)</label>
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
                                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="alert"></button>
                                    </div>
                                {% endfor %}
                            </div>
                          {% endif %}
                        {% endwith %}

                        <!-- Available Files -->
                        {% if show_files_flag %}
                        <div class="mb-4">
                            <h3 class="mb-3 text-white"><i class="bi bi-files"></i> Available Files</h3>
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

                        <!-- Processing Queue -->
                        <div>
                            <h3 class="mb-3 text-white"><i class="bi bi-gear"></i> Processing Queue</h3>
                            {% if processing_files or queue_files %}
                                <!-- Currently Processing -->
                                {% if processing_files %}
                                    <div class="mb-3">
                                        <h5 class="text-warning"><i class="bi bi-gear-fill"></i> Currently Processing</h5>
                                        <div class="list-group">
                                            {% for filename in processing_files %}
                                                <div class="list-group-item d-flex justify-content-between align-items-center">
                                                    <span>
                                                        <i class="bi bi-file-earmark-code"></i> {{ filename }}
                                                    </span>
                                                    <div class="spinner-border spinner-border-sm text-warning" role="status">
                                                        <span class="visually-hidden">Processing...</span>
                                                    </div>
                                                </div>
                                            {% endfor %}
                                        </div>
                                    </div>
                                {% endif %}
                                
                                <!-- Waiting in Queue -->
                                {% if queue_files %}
                                    <div class="mb-3">
                                        <h5 class="text-info"><i class="bi bi-clock"></i> Waiting in Queue</h5>
                                        <div class="list-group">
                                            {% for filename in queue_files %}
                                                <div class="list-group-item d-flex justify-content-between align-items-center">
                                                    <span>
                                                        <i class="bi bi-file-earmark-text"></i> {{ filename }}
                                                    </span>
                                                    <span class="badge bg-info">Queued</span>
                                                </div>
                                            {% endfor %}
                                        </div>
                                    </div>
                                {% endif %}
                            {% else %}
                                <div class="alert alert-secondary" role="alert">
                                    <i class="bi bi-check-circle"></i> No files currently being processed.
                                </div>
                            {% endif %}
                        </div>

                        {% endif %}
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
            custom_filename = pathlib.Path(
                request.form.get("filename", "").strip().lower()
            )
            final_filename = pathlib.Path(file.filename.lower())

            try:
                # Use custom filename, append the original file extension
                # final_filename = custom_filename.lower() + '.' + file.filename.lower().split('.')[-1]
                final_filename = custom_filename.with_suffix(final_filename.suffix)
            except Exception as e:
                pass  # Failed to parse custom filename, use original

            # Validate the final filename
            print("Final filename:", final_filename)
            if final_filename.name.startswith("."):
                flash("Invalid filename. Please provide a valid name.")
                return redirect(request.url)

            # filepath = os.path.join(app.config["UPLOAD_FOLDER"], final_filename)
            filepath = pathlib.Path(app.config["UPLOAD_FOLDER"]) / final_filename

            # Check if file already exists
            if filepath.exists():
                flash(
                    f"File '{final_filename}' already exists. Please choose a different name."
                )
                return redirect(request.url)

            file.save(filepath)

            # Add the file to the job queue for processing
            with job_queue_lock:
                job_queue.append(filepath)

            flash(f"File uploaded successfully as {final_filename}!")
            return redirect(url_for("upload_file"))

    # GET request: render the upload form and list available files
    files = os.listdir(app.config["UPLOAD_FOLDER"])

    with job_queue_lock:
        # Remove files that are currently being processed
        files = [
            f
            for f in files
            if (f not in in_processing_queue) and (not f.startswith("."))
        ]
        # Get files currently being processed
        processing_files = list(in_processing_queue)
        # Get files waiting in queue (extract just the filenames)
        queue_files = [os.path.basename(str(job)) for job in job_queue]

    return render_template_string(
        UPLOAD_FORM,
        files=files,
        show_files_flag=True,
        processing_files=processing_files,
        queue_files=queue_files,
    )


@app.route("/uploads/<path:filename>")
def download_file(filename):
    return send_from_directory(
        app.config["UPLOAD_FOLDER"], filename, as_attachment=True
    )


def background_worker():
    print("Background worker started...")

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

        if job.suffix in [".mov", ".mp4", ".avi", ".mkv", ".flv", ".wmv", ".webm"]:
            # Convert video files to mp4 x264 fps=10 format if they are not already

            out_fname = job.with_stem(f"{job.stem}_converted").with_suffix(
                ".mp4"
            )  # Change extension to .mp4

            job_exec = f'{FFMPEG_BIN} -y -noautorotate -i "{job}" -c:v libx264 -pix_fmt yuv420p' 
            job_exec += "-vf \"scale='if(gt(iw,ih),-2,720)':'if(gt(iw,ih),720,-2)'\""
            job_exec += f'-preset fast -crf 23 -an -r 10 "{out_fname}"'
            print("Prepared job command:", job_exec)

            pass
        else:
            # If the file is not a video, skip processing
            print(f"Skipping non-video file: {job}")
            continue

        try:
            # Example: run a shell command or process the job
            with job_queue_lock:
                in_processing_queue.add(out_fname.name)
            subprocess.run(job_exec, shell=True)
            with job_queue_lock:
                in_processing_queue.remove(out_fname.name)
        except Exception as e:
            print(f"Error processing job: {e}")

        print(f"Finished processing job: {job}")


worker_thread = threading.Thread(target=background_worker, daemon=True)
worker_thread.start()

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=80)
