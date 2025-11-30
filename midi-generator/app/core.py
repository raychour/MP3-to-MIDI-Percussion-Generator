import os
import subprocess
import librosa
import numpy as np
import soundfile as sf
from pathlib import Path
import shutil

def process_audio(file_path: str) -> str:
    """
    Main processing pipeline:
    1. Separate drums using Demucs
    2. Find loopable section
    3. Transcribe to MIDI
    """
    print(f"Processing {file_path}")
    
    # 1. Separate Drums
    # demucs -n htdemucs --two-stems=drums <file>
    # Output goes to separated/htdemucs/<filename>/drums.wav
    cmd = ["demucs", "-n", "htdemucs", "--two-stems=drums", file_path]
    print(f"Running Demucs: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    
    filename_stem = Path(file_path).stem
    # Demucs output structure: separated/htdemucs/{filename_stem}/drums.wav
    # Note: Demucs might normalize the filename, so we need to be careful. 
    # Usually it's safe to assume it uses the stem.
    drums_path = Path("separated") / "htdemucs" / filename_stem / "drums.wav"
    
    if not drums_path.exists():
        raise FileNotFoundError(f"Demucs failed to produce {drums_path}")

    # 2. Find Loopable Section
    # Load drums
    y, sr = librosa.load(drums_path, sr=None)
    
    # Heuristic: Find 4 bars of high activity
    # Estimate tempo
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    print(f"Estimated tempo: {tempo}")
    
    # 4 bars duration in seconds
    # 4 beats/bar * 4 bars = 16 beats
    # 60 / tempo = seconds per beat
    duration_4_bars = 16 * (60 / tempo)
    
    # Calculate onset envelope
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    times = librosa.times_like(onset_env, sr=sr)
    
    # Sliding window to find max energy
    # Convert duration to frame count
    hop_length = 512 # default for librosa
    window_frames = int(duration_4_bars * sr / hop_length)
    
    if window_frames >= len(onset_env):
        # File is shorter than 4 bars, take the whole thing
        start_frame = 0
        end_frame = len(onset_env)
    else:
        # Convolve to find window with max energy
        # Simple sum over window
        window_sum = np.convolve(onset_env, np.ones(window_frames), mode='valid')
        start_frame = np.argmax(window_sum)
        end_frame = start_frame + window_frames
        
    start_time = times[start_frame]
    end_time = times[min(end_frame, len(times)-1)]
    
    print(f"Selected loop: {start_time:.2f}s to {end_time:.2f}s")
    
    # Crop the audio
    y_loop = y[int(start_time*sr):int(end_time*sr)]
    loop_audio_path = f"temp_loop_{filename_stem}.wav"
    sf.write(loop_audio_path, y_loop, sr)
    
    # 3. Transcribe to MIDI using Omnizart
    # omnizart drum transcribe <file>
    print("Running Omnizart...")
    cmd_omni = ["omnizart", "drum", "transcribe", loop_audio_path]
    subprocess.run(cmd_omni, check=True)
    
    # Omnizart outputs to the same folder with .mid extension
    # e.g. temp_loop_{filename_stem}.mid
    midi_output = f"temp_loop_{filename_stem}.mid"
    
    if not os.path.exists(midi_output):
         raise FileNotFoundError(f"Omnizart failed to produce {midi_output}")
         
    return midi_output
