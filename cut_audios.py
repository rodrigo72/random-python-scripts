import os
from typing import List
from moviepy import AudioFileClip
import datetime
import subprocess
import platform

INPUT_FOLDER = 'input'
OUTPUT_FOLDER = 'output'
AUDIO_EXTS = ('.mp3', '.wav', '.aac', '.ogg', '.flac', '.m4a')


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
    
    print(f"Found {len(audio_paths)} audio file(s).\n")
    
    for idx, audio_path in enumerate(audio_paths, 1):
        print(f"\n{'='*60}")
        print(f"File {idx}/{len(audio_paths)}: {audio_path}")
        print(f"{'='*60}")
        
        try:
            audio_clip = AudioFileClip(audio_path)
            duration_sec = audio_clip.duration
            print(f"Duration: {duration_sec:.2f} seconds ({format_time(duration_sec)})")
        except Exception as e:
            print(f"Error loading audio: {e}")
            continue
        
        while True:
            listen = input("\nDo you want to listen to this audio? (z/x): ").strip().lower()
            if listen in ['z', 'x']:
                break
            print("Please enter 'z' or 'x'.")
        
        if listen == 'z':
            print("Opening audio in default player...")
            print("(You can pause/stop using your media player controls)")
            play_audio_file(audio_path)
            input("\nPress Enter when ready to continue...")
        
        while True:
            cut_audio = input("\nDo you want to cut this audio? (z/x): ").strip().lower()
            if cut_audio in ['z', 'x']:
                break
            print("Please enter 'z' or 'x'.")
        
        if cut_audio == 'x':
            audio_clip.close()
            continue
        
        while True:
            print("\n--- Audio Cutting ---")
            print("Enter timestamps in format 'hh:mm:ss', 'mm:ss' or 'ss' (seconds)")
            print(f"Audio duration: {duration_sec:.2f} seconds ({format_time(duration_sec)})")
            print("(Type 'q' or 'quit' at any prompt to skip this file)")
            
            try:
                start_ts = input("Start timestamp: ").strip()
                if start_ts.lower() in ['q', 'quit']:
                    print("Skipping this file...")
                    break
                
                end_ts = input("End timestamp: ").strip()
                if end_ts.lower() in ['q', 'quit']:
                    print("Skipping this file...")
                    break
                
                start_sec = parse_timestamp(start_ts)
                end_sec = parse_timestamp(end_ts)
                
                if start_sec < 0 or end_sec > duration_sec or start_sec >= end_sec:
                    print(f"Invalid timestamps. Must be: 0 <= start < end <= {duration_sec:.2f}s")
                    continue
                
                while True:
                    name_choice = input("\nUse automatic name? (z/x): ").strip().lower()
                    if name_choice in ['z', 'x']:
                        break
                    print("Please enter 'z' or 'x'.")
                
                if name_choice == 'z':
                    output_name = generate_output_name(audio_path, start_sec, end_sec)
                else:
                    custom_name = input("Enter filename: ").strip()
                    if not os.path.splitext(custom_name)[1]:
                        original_ext = os.path.splitext(audio_path)[1]
                        output_name = custom_name + original_ext
                    else:
                        output_name = custom_name
                
                output_path = os.path.join(OUTPUT_FOLDER, output_name)
                
                print(f"\nCutting audio from {format_time(start_sec)} to {format_time(end_sec)}...")
                print(f"Saving to: {output_path}")
                
                cut_clip = audio_clip.subclipped(start_sec, end_sec)
                cut_clip.write_audiofile(output_path, logger=None)
                cut_clip.close()
                
                print("✓ Audio saved successfully")
            except ValueError as e:
                print(f"Error: {e}")
                continue
            except Exception as e:
                print(f"Error cutting audio: {e}")
                continue
            
            while True:
                another_cut = input("\nMake another cut from this file? (z/x): ").strip().lower()
                if another_cut in ['z', 'x']:
                    break
                print("Please enter 'z' or 'x'.")
            
            if another_cut == 'x':
                break
        
        audio_clip.close()
    
    print("\n" + "="*60)
    print("Processing complete.")
    print("="*60)


if __name__ == '__main__':
    main()
