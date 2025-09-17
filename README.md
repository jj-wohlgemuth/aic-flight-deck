# Simple Web GUI Drag & Drop App for the AIC API

> **Disclaimer:**  
> This tool is a **community project**, created and was created privately by me.
> It is **not an official AI-coustics product**, and **AI-coustics does not maintain or support it**.  
> Please use it at your own discretion.

This a Python app with a web GUI (Flask) that lets you drag & drop files for upload and processing.

## User Quickstart

1. If you don't have a API Key yet, you can get one for free at <https://developers.ai-coustics.io/signup>.

### How to open the app on macOS (unsigned)

If you see a warning that the app cannot be opened because it is from an unidentified developer:

1. Attempt to open the app. A message might prevent you from doing that. Ignore the message.
2. Now go to **System Settings > Privacy & Security**.
3. Scroll down to the "Security" section.
4. You should see a message about the blocked app with an **Open Anyway** button—click it.
5. Confirm in the next dialog to open the app.

## Dev Quickstart

### 1. Create and activate a virtual environment

```sh
python3 -m venv .aic-flight-deck
source .aic-flight-deck/bin/activate
```

### 2. Install dependencies

```sh
pip install .
```

### 3. Run the app

```sh
python app.py
```
Or to run with a standalone browser window (mini Chrome-like):

```sh
python run_gui.py
```

Open your browser at [http://127.0.0.1:5000](http://127.0.0.1:5000)

### 4. Packaging as an executable

You can use [PyInstaller](https://pyinstaller.org/) to build a standalone executable:

```sh
pip install pyinstaller
pyinstaller run_gui.spec
```

The executable will be in the `dist/` folder.