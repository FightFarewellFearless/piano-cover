from music2midi.model import Music2MIDI
import torch
import IPython.display as ipd
from music2midi.plot_midi import plot_midi_sequence
import soundfile as sf
import os

device = "cuda" if torch.cuda.is_available() else "cpu"

# SESUAIKAN PATH INI:
# Karena model di-download ke folder 'my_project' (lokasi skrip ini)
ckpt_path = "model.ckpt" 

# Config biasanya ada di dalam repo music2midi
config_path = "../music2midi/config.yaml"

model = Music2MIDI.load_from_checkpoint(ckpt_path, config_path=config_path)
model.to(device).eval()
print("model loaded successfully")

# Pastikan file audio input ada di folder yang sama (my_project)
input_audio_path = '../audiosep_output/vocals_output.mp3'
midi_data = model.generate(input_audio_path)

fs = 44100
midi_synth = midi_data.fluidsynth(fs)
ipd.display(ipd.Audio(midi_synth, rate=fs))

plot_midi_sequence(midi_data)


# save midi file
midi_data.write("midi.mid")
# save audio file
sf.write("audio.mp3", midi_synth, fs)