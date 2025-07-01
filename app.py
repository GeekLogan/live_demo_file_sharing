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

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB limit
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
                                    <input type="file" name="file" class="form-control" required>
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
        if file.filename == "":
            flash("No selected file")
            return redirect(request.url)
        if file:
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
            file.save(filepath)
            flash(f"File {file.filename} uploaded successfully!")
            return redirect(url_for("upload_file"))
    files = os.listdir(app.config["UPLOAD_FOLDER"])
    return render_template_string(UPLOAD_FORM, files=files)


@app.route("/uploads/<path:filename>")
def download_file(filename):
    return send_from_directory(
        app.config["UPLOAD_FOLDER"], filename, as_attachment=True
    )


if __name__ == "__main__":
    app.run(debug=True)
