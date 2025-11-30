import os
import numpy as np
import subprocess
import librosa
import soundfile as sf
from pathlib import Path
import shutil
import matplotlib.pyplot as plt
import librosa.display

def process_audio(file_path: str, progress_callback=None, quantization: int = 16, mode: str = "midi") -> tuple[str, float, str]:
    """
    Main processing pipeline:
    1. Separate audio using Demucs
    2. If MIDI: Find loopable section & Transcribe
    3. If Audio: Return separated stem
    """
    def report(p, m):
        if progress_callback:
            progress_callback(p, m)
            
    print(f"Processing {file_path} with mode={mode}, quantization=1/{quantization}")
    
    # Determine Demucs target
    demucs_target = "drums" # default
    if mode == "vocals":
        demucs_target = "vocals"
    elif mode == "bass":
        demucs_target = "bass"
    elif mode == "drums":
        demucs_target = "drums"
        
    report(5, f"Separating {demucs_target} (this may take a while)...")
    
    # 1. Separate Audio
    # demucs -n htdemucs --two-stems=<target> <file>
    cmd = ["demucs", "-n", "htdemucs", f"--two-stems={demucs_target}", file_path]
    print(f"Running Demucs: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    
    filename_stem = Path(file_path).stem
    stem_path = Path("separated") / "htdemucs" / filename_stem / f"{demucs_target}.wav"
    
    if not stem_path.exists():
        raise FileNotFoundError(f"Demucs failed to produce {stem_path}")

    # Load audio for spectrogram/analysis
    y, sr = librosa.load(stem_path, sr=None)
    
    # If Audio Mode, return the stem directly
    if mode != "midi":
        report(90, "Generating spectrogram...")
        
        # Generate Spectrogram
        plt.figure(figsize=(10, 4))
        D = librosa.amplitude_to_db(np.abs(librosa.stft(y)), ref=np.max)
        librosa.display.specshow(D, sr=sr, x_axis='time', y_axis='log')
        plt.colorbar(format='%+2.0f dB')
        plt.title(f'Spectrogram of Extracted {demucs_target.capitalize()}')
        plt.tight_layout()
        
        spectrogram_output = f"spectrogram_{filename_stem}.png"
        plt.savefig(spectrogram_output)
        plt.close()
        
        # Copy stem to output location
        output_wav = f"output_{filename_stem}_{demucs_target}.wav"
        shutil.copy(stem_path, output_wav)
        
        report(100, "Done!")
        return output_wav, 0.0, spectrogram_output

    # --- MIDI MODE (Existing Logic) ---
    report(60, "Analyzing audio for loops...")

    # Heuristic: Find 4 bars of high activity, prioritizing the "beat" (Kick)
    # Filter for bass to find the "beat" (4 on the floor)
    import scipy.signal
    # Low-pass filter at 200Hz to focus on Kick/Bass
    sos = scipy.signal.butter(4, 200, 'lp', fs=sr, output='sos')
    y_low = scipy.signal.sosfilt(sos, y)
    
    # Estimate tempo (use full signal for better tempo estimation)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    if isinstance(tempo, np.ndarray):
        tempo = float(tempo)
    print(f"Estimated tempo: {tempo}")
    
    report(70, f"Tempo detected: {tempo:.1f} BPM. Finding best loop...")
    
    # 4 bars duration in seconds
    duration_4_bars = 16 * (60 / tempo)
    
    # Calculate onset envelope on the LOW-PASSED signal to find the "groove"
    onset_env = librosa.onset.onset_strength(y=y_low, sr=sr)
    times = librosa.times_like(onset_env, sr=sr)
    
    # Sliding window to find max energy
    hop_length = 512 
    window_frames = int(duration_4_bars * sr / hop_length)
    
    if window_frames >= len(onset_env):
        start_frame = 0
        end_frame = len(onset_env)
    else:
        window_sum = np.convolve(onset_env, np.ones(window_frames), mode='valid')
        start_frame = np.argmax(window_sum)
        end_frame = start_frame + window_frames
        
    start_time = times[start_frame]
    end_time = times[min(end_frame, len(times)-1)]
    
    print(f"Selected loop: {start_time:.2f}s to {end_time:.2f}s")
    
    # Crop the audio (original full-frequency audio)
    y_loop = y[int(start_time*sr):int(end_time*sr)]
    loop_audio_path = f"temp_loop_{filename_stem}.wav"
    sf.write(loop_audio_path, y_loop, sr)
    
    # 3. Transcribe to MIDI using Librosa (Custom Logic)
    print("Transcribing with Librosa...")
    report(85, "Transcribing to MIDI...")
    
    # Load the loop audio
    y_loop, sr = librosa.load(loop_audio_path, sr=None)
    
    # Detect onsets
    onset_frames = librosa.onset.onset_detect(y=y_loop, sr=sr, backtrack=True)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)
    
    # Create MIDI file
    import mido
    from mido import MidiFile, MidiTrack, Message, MetaMessage
    
    mid = MidiFile()
    track = MidiTrack()
    mid.tracks.append(track)
    
    track.append(MetaMessage('set_tempo', tempo=mido.bpm2tempo(tempo)))
    
    last_time = 0
    ticks_per_beat = mid.ticks_per_beat
    
    def time_to_ticks(t):
        return int(t * (tempo / 60) * ticks_per_beat)
        
    sorted_onsets = sorted(onset_times)
    
    # Create a list of all events: (time, type, note, velocity)
    events = []
    
    for onset_time in sorted_onsets:
        # Analyze frequency content at this onset
        start_sample = int(onset_time * sr)
        end_sample = min(start_sample + int(0.05 * sr), len(y_loop))
        
        if end_sample > start_sample:
            segment = y_loop[start_sample:end_sample]
            
            # Calculate STFT for Band Energy Ratio
            # n_fft=2048 is default. Bin size ~ 21.5 Hz (at 44.1k)
            S = np.abs(librosa.stft(segment))
            
            # Low Band: < 150 Hz (approx first 7 bins)
            # High Band: > 2000 Hz (approx bin 93+)
            low_energy = np.sum(S[:7, :])
            high_energy = np.sum(S[93:, :])
            
            # Spectral Centroid for refinement
            centroid = librosa.feature.spectral_centroid(S=S, sr=sr)
            avg_centroid = np.mean(centroid)
            
            # Classification Logic
            if low_energy > high_energy * 0.8: # Tunable threshold, favor kicks slightly
                note = 36 # Kick
            else:
                # Distinguish Snare vs HiHat
                if avg_centroid < 3500:
                    note = 38 # Snare
                else:
                    note = 42 # Closed HiHat
        else:
            note = 38
            
        # Quantize
        abs_ticks = time_to_ticks(onset_time)
        if quantization > 0:
             grid_ticks = int(ticks_per_beat * 4 / quantization)
             abs_ticks = round(abs_ticks / grid_ticks) * grid_ticks
        
        # Note Off (fixed duration 0.1s)
        duration_ticks = time_to_ticks(0.1)
        off_ticks = abs_ticks + duration_ticks
        
        # Add Note On
        events.append((abs_ticks, 'note_on', note, 100))
        # Add Note Off
        events.append((off_ticks, 'note_off', note, 0))
        
    # Sort events by time
    events.sort(key=lambda x: x[0])
    
    last_ticks = 0
    
    for abs_ticks, msg_type, note, velocity in events:
        delta_ticks = abs_ticks - last_ticks
        # Ensure non-negative
        if delta_ticks < 0:
            delta_ticks = 0
            
        track.append(Message(msg_type, note=note, velocity=velocity, time=delta_ticks))
        last_ticks = abs_ticks

    midi_output = f"output_{filename_stem}.mid"
    mid.save(midi_output)
    
    # Generate Spectrogram
    plt.figure(figsize=(10, 4))
    # Use the loop audio we already loaded
    D = librosa.amplitude_to_db(np.abs(librosa.stft(y_loop)), ref=np.max)
    librosa.display.specshow(D, sr=sr, x_axis='time', y_axis='log')
    plt.colorbar(format='%+2.0f dB')
    plt.title('Spectrogram of Extracted Loop')
    plt.tight_layout()
    
    spectrogram_output = f"spectrogram_{filename_stem}.png"
    plt.savefig(spectrogram_output)
    plt.close()
    
    report(100, "Done!")
         
    return midi_output, tempo, spectrogram_output
