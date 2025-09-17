from flask import Flask, render_template, request
import os
from api import process_files_parallel, EnhancementModel

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    import os
    default_download_folder = os.path.join(os.path.expanduser('~'), 'Downloads')
    default_api_key = os.environ.get('AI_COUSTICS_API_KEY', '')
    return render_template('index.html', default_download_folder=default_download_folder, default_api_key=default_api_key)

@app.route('/upload', methods=['POST'])
def upload():
    files = request.files.getlist('files[]')
    api_key = request.form.get('apiKey', '')
    output_folder = request.form.get('outputFolder', UPLOAD_FOLDER)
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    model_arch = request.form.get('enhancementModel', 'LARK_V2')
    temp_paths = []
    output_files = []
    for file in files:
        filename = file.filename if file.filename is not None else "unnamed"
        temp_path = os.path.join(output_folder, 'temp_' + filename)
        file.save(temp_path)
        temp_paths.append(temp_path)
        output_file_name = f"{os.path.splitext(filename)[0]}_{model_arch}{os.path.splitext(filename)[1]}"
        output_file_name = output_file_name.replace('temp_', '')
        output_file_path = os.path.join(output_folder, output_file_name)
        output_files.append(output_file_path)
    failed_files = process_files_parallel(
        audio_files=temp_paths,
        model_arch=EnhancementModel[model_arch],
        output_folder_full_path=output_folder,
        api_key=api_key
    )
    for temp_path in temp_paths:
        try:
            os.remove(temp_path)
        except Exception:
            pass
    return {'status': 'success', 'files': output_files, 'failed_files': failed_files}

if __name__ == '__main__':
    app.run(debug=True)
