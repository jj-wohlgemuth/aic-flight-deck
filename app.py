from flask import Flask, render_template, request, jsonify
import uuid
import threading
import os
from api import process_files_parallel, EnhancementModel
import soundfile as sf
import resampy
import numpy as np

app = Flask(__name__)
DOWNLOADS_FOLDER = os.path.join(os.path.expanduser("~"), "Downloads")
AIC_API_FS_HZ = 32000

# In-memory job store: {job_id: {'status': str, 'files': list, 'failed_files': list}}
job_store = {}


@app.route("/")
def index():
    import os

    default_download_folder = DOWNLOADS_FOLDER
    default_api_key = os.environ.get("AI_COUSTICS_API_KEY", "")
    return render_template(
        "index.html",
        default_download_folder=default_download_folder,
        default_api_key=default_api_key,
    )


@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files[]")
    api_key = request.form.get("apiKey", "")
    output_folder = request.form.get("outputFolder", DOWNLOADS_FOLDER)
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    model_arch = request.form.get("enhancementModel", "LARK_V2")
    mix_percent = float(request.form.get("mixPercent", "100"))
    temp_paths = []
    output_files = []
    for file in files:
        filename = file.filename if file.filename is not None else "unnamed"
        temp_path = os.path.join(output_folder, "temp_" + filename)
        if file.content_type is not None and "audio" in file.content_type:
            audio_pcm, fs_hz = sf.read(file)
            audio_pcm = np.mean(audio_pcm, axis=1) if audio_pcm.ndim > 1 else audio_pcm
            audio_pcm_resampled = resampy.resample(audio_pcm, fs_hz, AIC_API_FS_HZ)
            sf.write(temp_path, audio_pcm_resampled, AIC_API_FS_HZ)
        else:
            file.save(temp_path)
        temp_paths.append(temp_path)
        output_file_name = f"{os.path.splitext(filename)[0]}_{model_arch}{os.path.splitext(filename)[1]}"
        output_file_name = output_file_name.replace("temp_", "")
        output_file_path = os.path.join(output_folder, output_file_name)
        output_files.append(output_file_path)

    job_id = str(uuid.uuid4())
    job_store[job_id] = {
        "status": "processing",
        "files": output_files,
        "failed_files": [],
    }

    def process_job():
        failed_files = process_files_parallel(
            audio_files=temp_paths,
            model_arch=EnhancementModel[model_arch],
            mix_percent=mix_percent,
            output_folder_full_path=output_folder,
            api_key=api_key,
        )
        for temp_path in temp_paths:
            try:
                os.remove(temp_path)
            except Exception:
                pass
        # Only include files that did not fail
        successful_files = [
            f
            for f in output_files
            if all(f.split(":")[0] not in fail for fail in failed_files)
        ]
        job_store[job_id]["files"] = successful_files
        job_store[job_id]["failed_files"] = failed_files
        job_store[job_id]["status"] = "done"

    threading.Thread(target=process_job, daemon=True).start()
    return jsonify({"job_id": job_id})


@app.route("/status", methods=["GET"])
def status():
    job_id = request.args.get("job_id")
    job = job_store.get(job_id)
    if not job:
        return jsonify({"error": "Invalid job ID"}), 404
    return jsonify(job)


if __name__ == "__main__":
    app.run(debug=True)
