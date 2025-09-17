import asyncio
from pathlib import Path
from enum import Enum
import aiofiles
from aiofiles import os as aiofiles_os
import aiohttp
import certifi
import ssl
import time
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import traceback
import json


API_URL = "https://api.ai-coustics.io/v2"
CHUNK_SIZE = 1024
MAX_WORKERS = 10
TIMEOUT_FACTOR_S_PER_MB = 60
TIMEOUT_FACTOR_S_PER_MB_COMPRESSED = TIMEOUT_FACTOR_S_PER_MB * 10
COMPRESSED_EXTENSIONS = ('.aac', '.opus', '.ogg', '.mp3', '.flac', '.mp4')
POLLING_INTERVAL_S = 5

lock = Lock()


class EnhancementModel(Enum):
    LARK_V2 = "LARK_V2"
    FINCH = "FINCH"


class ApiParams:
    def __init__(
        self,
        mix_percent: float,
        enhancement_model: EnhancementModel = EnhancementModel.LARK_V2,
    ):
        self.mix_percent = mix_percent
        self.enhancement_model = enhancement_model


async def __download_enhanced_media(
    url: str,
    output_file_path: str,
    api_key: str
) -> tuple[int, str|None]:
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    async with aiohttp.ClientSession(headers={"X-API-Key": api_key}, connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
        async with session.get(url) as response:
            if response.status != 200:
                await response.text()
                return response.status, response.reason

            await aiofiles_os.makedirs(Path(output_file_path).parent, exist_ok=True)
            async with aiofiles.open(output_file_path, "wb") as f:
                async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                    await f.write(chunk)
    print(f"Download successfully to: {output_file_path}")
    return response.status, response.reason
    
def __process_file(
    input_file_path: str, output_file_path: str, params: ApiParams, api_key: str
) -> None:
    arguments = {
        "loudness_target_level": -14,
        "true_peak": -1,
        "enhancement_level": int(params.mix_percent),
        #"transcode_kind": expected_media_format,
        "enhancement_model": params.enhancement_model.value,
        "file_name": input_file_path
    }

    url = f"{API_URL}/medias"
    uid = asyncio.run(
        __upload_and_enhance(
            url,
            input_file_path,
            arguments,
            api_key
        )
    )

    file_size_bytes = os.path.getsize(input_file_path)
    file_size_mb = file_size_bytes / (1024 * 1024)
    timeout_factor = TIMEOUT_FACTOR_S_PER_MB_COMPRESSED if input_file_path.lower().endswith(COMPRESSED_EXTENSIONS) else TIMEOUT_FACTOR_S_PER_MB
    timeout_seconds = int(file_size_mb * timeout_factor)
    response_code = 412
    reason = f"{url} call failed"
    start_time = time.time()
    while response_code == 412 and time.time() - start_time < timeout_seconds:
        time.sleep(POLLING_INTERVAL_S)
        url = f"{API_URL}/medias/{uid}/file"
        response_code, reason = asyncio.run(
            __download_enhanced_media(
                url,
                output_file_path,
                api_key
            )
        )
    if response_code == 412:
        raise TimeoutError(
            f"Download timed out after {timeout_seconds} seconds (file size: {file_size_mb:.2f} MB). Please try again."
        )
    elif response_code != 200:
        raise Exception(f"Failed to download enhanced media: {reason}")


async def __upload_and_enhance(
    url: str,
    file_path: str,
    arguments: dict[str, str],
    api_key: str
) -> str | None:
    form_data = aiohttp.FormData()
    form_data.add_field("media_enhancement", json.dumps(arguments))

    async with aiofiles.open(file_path, "rb") as file:
        file_content = await file.read()
        form_data.add_field(
            "file",
            file_content,
            content_type="application/octet-stream",
            filename=Path(file_path).name,
        )

    ssl_context = ssl.create_default_context(cafile=certifi.where())
    async with aiohttp.ClientSession(headers={"X-API-Key": api_key}, connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
        async with session.post(url, data=form_data) as response:
            if response.status != 201:
                response_text = await response.text()
                print(f"Error occured: {response_text}")
                return None

            response_json = await response.json()
            uid = response_json["uid"]
            print(f"Uploaded file's uid: {uid}")
            return uid


def __process_file_parallel(
    input_file_path: str,
    output_folder_full_path: str,
    enhancement_model: EnhancementModel,
    api_key: str,
    failed_files: list[str]
):
    try:
        if not os.path.exists(output_folder_full_path):
            os.makedirs(output_folder_full_path)
        # Process files with extensions for AAC LC, Opus, Vorbis, MPEG Audio, FLAC, PCM
        allowed_extensions = ('.wav', '.aac', '.opus', '.ogg', '.mp3', '.flac', '.pcm', '.mp4')
        if input_file_path.lower().endswith(allowed_extensions):
            output_file_name = f"{os.path.splitext(input_file_path)[0]}_{enhancement_model.value}{os.path.splitext(input_file_path)[1]}".replace('temp_', '')
            output_file_path = os.path.join(output_folder_full_path, output_file_name)
            __process_file(
                input_file_path,
                output_file_path,
                params=ApiParams(mix_percent=100.0, enhancement_model=enhancement_model),
                api_key=api_key
            )
        else:
            raise ValueError(f"Unsupported file extension for file: {input_file_path}, supported extensions are: {allowed_extensions}")
    except Exception as e:
        print(f"Error processing {input_file_path}: {e}")
        failed_files.append(f"{input_file_path}: {e}")

def __safe_process(args):
    input_file_path, output_folder_full_path, model_arch, api_key, failed_files = args
    __process_file_parallel(input_file_path, output_folder_full_path, model_arch, api_key, failed_files)

def process_files_parallel(audio_files: list[str], model_arch: EnhancementModel, output_folder_full_path: str, api_key: str) -> list[str]:
    failed_files = []
    args_list = [(file, output_folder_full_path, model_arch, api_key, failed_files) for file in audio_files]
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        executor.map(__safe_process, args_list)
    print(f"Processed {len(audio_files) - len(failed_files)} out of {len(audio_files)} files.")
    if failed_files:
        print("Failed files:", failed_files)
    return failed_files
