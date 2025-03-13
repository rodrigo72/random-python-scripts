import os
import argparse
import ffmpeg
import whisper
from googletrans import Translator
import time


"""
python3 add_subtitles.py "video (1).mp4" --model medium --lang pt --output subtitled_video.mp4
model sizes: tiny, base, small, medium, large
"""


def extract_audio(video_path):
    base = os.path.splitext(video_path)[0]
    audio_file = f"{base}.wav"
    ffmpeg.input(video_path).output(audio_file).run(overwrite_output=True)
    return audio_file


def get_audio(input_file):
    ext = os.path.splitext(input_file)[1].lower()
    if ext in ['.mp3', '.wav']:
        return input_file
    else:
        return extract_audio(input_file)


def transcribe_audio(audio_path, model_size="small"):
    model = whisper.load_model(model_size)
    result = model.transcribe(audio_path)
    return result["segments"]


def safe_translate(text, translator, dest_lang, retries=3):
    for attempt in range(1, retries + 1):
        try:
            translation = translator.translate(text, dest=dest_lang)
            return translation.text
        except Exception as e:
            print(f"Error translating text: {text}\nError: {e}. Retrying ({attempt}/{retries})...")
            time.sleep(1)
    return text


def translate_segments(segments, dest_lang="pt"):
    translator = Translator()
    for seg in segments:
        seg["translated_text"] = safe_translate(seg["text"], translator, dest_lang)
    return segments


def format_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def generate_srt(segments, srt_file):
    srt_lines = []
    for idx, seg in enumerate(segments, start=1):
        start_time = format_time(seg["start"])
        end_time = format_time(seg["end"])
        text = seg.get("translated_text", "").strip()
        srt_lines.append(f"{idx}")
        srt_lines.append(f"{start_time} --> {end_time}")
        srt_lines.append(text)
        srt_lines.append("")
    with open(srt_file, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))
    return srt_file


def burn_subtitles(input_file, srt_file, output_file):
    ext = os.path.splitext(input_file)[1].lower()
    if ext in ['.mp3', '.wav']:
        print("Input is an audio file; skipping subtitle burn step.")
        return input_file
    ffmpeg.input(input_file).output(output_file, vf=f"subtitles={srt_file}").run(overwrite_output=True)
    return output_file


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe and translate audio/video files using Whisper and burn subtitles."
    )
    parser.add_argument("input_file", help="Path to the input video or audio file (e.g., .mp4, .mp3)")
    parser.add_argument("--model", default="small", help="Whisper model size (e.g., tiny, base, small, medium, large). Default: small")
    parser.add_argument("--lang", default="pt", help="Target translation language (default: pt for Portuguese)")
    parser.add_argument("--output", default=None, help="Output video file name (only used if input is a video)")
    
    args = parser.parse_args()

    input_file = args.input_file
    model_size = args.model
    target_lang = args.lang
    base = os.path.splitext(input_file)[0]
    
    if args.output:
        output_file = args.output
    else:
        output_file = f"{base}_with_subtitles.mp4"

    print("Processing input file for audio...")
    audio_file = get_audio(input_file)
    
    print(f"Transcribing audio using Whisper model '{model_size}'...")
    segments = transcribe_audio(audio_file, model_size=model_size)
    
    print(f"Translating transcription to '{target_lang}'...")
    segments = translate_segments(segments, dest_lang=target_lang)
    
    srt_file = f"{base}_{target_lang}.srt"
    print("Generating SRT file...")
    generate_srt(segments, srt_file)
    
    print("Burning subtitles into video (if applicable)...")
    final_output = burn_subtitles(input_file, srt_file, output_file)
    
    print("Process completed.")
    print("Result file:", final_output)


if __name__ == "__main__":
    main()
