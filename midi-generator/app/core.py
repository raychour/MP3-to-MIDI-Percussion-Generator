import os
import numpy as np
import subprocess
import librosa
import soundfile as sf
from pathlib import Path
import shutil

def process_audio(file_path: str, progress_callback=None) -> tuple[str, float]:
    """
    Main processing pipeline:
    1. Separate drums using Demucs
    2. Find loopable section
    3. Transcribe to MIDI
    """
    def report(p, m):
        if progress_callback:
            progress_callback(p, m)
            
    print(f"Processing {file_path}")
    report(5, "Separating drums (this may take a while)...")
    
    # 1. Separate Drums
    # demucs -n htdemucs --two-stems=drums <file>
    # Output goes to separated/htdemucs/<filename>/drums.wav
    cmd = ["demucs", "-n", "htdemucs", "--two-stems=drums", file_path]
    print(f"Running Demucs: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    
    report(60, "Analyzing audio for loops...")
    
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
            
        # Add Note On
        events.append((onset_time, 'note_on', note, 100))
        # Add Note Off (0.1s later)
        events.append((onset_time + 0.1, 'note_off', note, 0))
        
    # Sort events by time
    events.sort(key=lambda x: x[0])
    
    last_time = 0
    
    for time, msg_type, note, velocity in events:
        delta_time = time - last_time
        # Ensure non-negative (floating point errors might give -1e-10)
        if delta_time < 0:
            delta_time = 0
            
        delta_ticks = time_to_ticks(delta_time)
        
        track.append(Message(msg_type, note=note, velocity=velocity, time=delta_ticks))
        last_time = time

    midi_output = f"output_{filename_stem}.mid"
    mid.save(midi_output)
    
    report(100, "Done!")
         
    return midi_output, tempo
