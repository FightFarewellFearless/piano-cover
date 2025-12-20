from music2midi.model import Music2MIDI
import torch
import IPython.display as ipd
from music2midi.plot_midi import plot_midi_sequence
import soundfile as sf


device = "cuda" if torch.cuda.is_available() else "cpu"
ckpt_path = "music2midi/model.ckpt"  # change this to the downloaded checkpoint file path
model = Music2MIDI.load_from_checkpoint(ckpt_path, config_path="config.yaml")
model.to(device).eval()
print("model loaded successfully")

input_audio_path = './music.mp3'
midi_data = model.generate(input_audio_path)

fs = 44100
midi_synth = midi_data.fluidsynth(fs)
ipd.display(ipd.Audio(midi_synth, rate=fs))

plot_midi_sequence(midi_data)


# save midi file
midi_data.write("midi.mid")
# save audio file
sf.write("audio.mp3", midi_synth, fs)