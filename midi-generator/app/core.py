import os
import numpy as np
import subprocess
import librosa
import soundfile as sf
from pathlib import Path
import shutil

def process_audio(file_path: str) -> tuple[str, float]:
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
    if isinstance(tempo, np.ndarray):
        tempo = float(tempo)
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
    
    # 3. Transcribe to MIDI using Librosa (Custom Logic)
    print("Transcribing with Librosa...")
    
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
    
    # Simple heuristic to distinguish Kick vs Snare/HiHat
    # We look at the spectral centroid of the audio segment around the onset
    
    last_time = 0
    ticks_per_beat = mid.ticks_per_beat
    
    # Convert seconds to ticks
    # ticks = seconds * (tempo / 60) * ticks_per_beat
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
            centroid = librosa.feature.spectral_centroid(y=segment, sr=sr)
            avg_centroid = np.mean(centroid)
            
            if avg_centroid < 1500:
                note = 36 # Kick
            elif avg_centroid < 3000:
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
         
    return midi_output, tempo
