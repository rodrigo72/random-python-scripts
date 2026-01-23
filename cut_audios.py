import os
from typing import List, Set
from moviepy import AudioFileClip
import datetime
import subprocess
import platform
import sys

INPUT_FOLDER = r'C:\Users\rodri\Desktop\phone_audios'
OUTPUT_FOLDER = 'output'
HISTORY_FILE = 'processed_history.txt'
AUDIO_EXTS = ('.mp3', '.wav', '.aac', '.ogg', '.flac', '.m4a')


def load_history() -> Set[str]:
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())

def save_to_history(file_path: str):
    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
        f.write(file_path + '\n')

def clear_history():
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)

def get_audio_paths(input_folder: str) -> List[str]:
    audio_paths = []
    for root, _, files in os.walk(input_folder):
        for file in files:
            if file.lower().endswith(AUDIO_EXTS):
                audio_paths.append(os.path.join(root, file))
    return audio_paths

def play_audio_file(file_path: str):
    system = platform.system()
    try:
        if system == 'Windows':
            os.startfile(file_path)
        elif system == 'Darwin':
            subprocess.run(['open', file_path])
        else:
            subprocess.run(['xdg-open', file_path])
        return True
    except Exception as e:
        print(f"Error opening audio player: {e}")
        return False

def parse_timestamp(timestamp: str) -> float:
    parts = timestamp.strip().split(':')
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    elif len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    elif len(parts) == 1:
        return float(parts[0])
    else:
        raise ValueError("Invalid timestamp format")

def generate_output_name(original_path: str, start_sec: float, end_sec: float) -> str:
    base_name = os.path.splitext(os.path.basename(original_path))[0]
    ext = os.path.splitext(original_path)[1]
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_name}_cut_{int(start_sec)}s-{int(end_sec)}s_{timestamp}{ext}"

def format_time(seconds: float) -> str:
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"

def main():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)    
    audio_paths = get_audio_paths(INPUT_FOLDER)
    
    if not audio_paths:
        print(f"No audio files found in '{INPUT_FOLDER}' folder.")
        return

    history = load_history()
    skip_mode = False
    
    if history:
        print(f"Found {len(history)} previously processed files.")
        choice = input("History found! [S]kip processed, [P]rocess all anyway, or [R]eset history? ").strip().lower()
        if choice == 's':
            skip_mode = True
        elif choice == 'r':
            clear_history()
            history = set()
            print("History cleared.")
    
    print(f"\nFound {len(audio_paths)} total audio file(s).")
    
    for idx, audio_path in enumerate(audio_paths, 1):
        if skip_mode and audio_path in history:
            continue

        print(f"\n{'='*60}")
        print(f"File {idx}/{len(audio_paths)}: {audio_path}")
        print("Commands: [z] Yes, [x] No, [q] Quit Entirely")
        print(f"{'='*60}")
        
        try:
            audio_clip = AudioFileClip(audio_path)
            duration_sec = audio_clip.duration
            print(f"Duration: {duration_sec:.2f}s ({format_time(duration_sec)})")
        except Exception as e:
            print(f"Error loading audio: {e}")
            continue
        
        while True:
            listen = input("\nListen to this audio? (z/x/q): ").strip().lower()
            if listen == 'q': sys.exit("Exiting script...")
            if listen in ['z', 'x']: break
        
        if listen == 'z':
            play_audio_file(audio_path)
            input("Press Enter when ready to continue...")
        
        while True:
            cut_audio = input("Cut this audio? (z/x/q): ").strip().lower()
            if cut_audio == 'q': sys.exit("Exiting script...")
            if cut_audio in ['z', 'x']: break
        
        if cut_audio == 'x':
            save_to_history(audio_path)
            audio_clip.close()
            continue
        
        while True:
            print(f"\n--- Audio Cutting ({format_time(duration_sec)}) ---")
            try:
                start_ts = input("Start timestamp (or 'q' to skip file): ").strip().lower()
                if start_ts in ['q', 'quit']: break
                
                end_ts = input("End timestamp (or 'q' to skip file): ").strip().lower()
                if end_ts in ['q', 'quit']: break
                
                start_sec = parse_timestamp(start_ts)
                end_sec = parse_timestamp(end_ts)
                
                if not (0 <= start_sec < end_sec <= duration_sec):
                    print(f"Invalid range! Must be within 0 and {duration_sec:.2f}s")
                    continue
                
                name_choice = input("Use automatic name? (z/x/q): ").strip().lower()
                if name_choice == 'q': sys.exit("Exiting script...")
                
                if name_choice == 'z':
                    output_name = generate_output_name(audio_path, start_sec, end_sec)
                else:
                    custom_name = input("Enter filename: ").strip()
                    output_name = custom_name if os.path.splitext(custom_name)[1] else custom_name + os.path.splitext(audio_path)[1]
                
                output_path = os.path.join(OUTPUT_FOLDER, output_name)
                print(f"Saving to: {output_path}...")
                
                cut_clip = audio_clip.subclipped(start_sec, end_sec)
                cut_clip.write_audiofile(output_path, logger=None)
                cut_clip.close()
                print("✓ Saved.")

                another = input("\nAnother cut from THIS file? (z/x/q): ").strip().lower()
                if another == 'q': sys.exit("Exiting script...")
                if another == 'x': break

            except ValueError as e:
                print(f"Input Error: {e}")
            except Exception as e:
                print(f"Processing Error: {e}")

        save_to_history(audio_path)
        audio_clip.close()
    
    print(f"\n{'='*60}\nProcessing complete.\n{'='*60}")


if __name__ == '__main__':
    main()
